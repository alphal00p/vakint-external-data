#!/usr/bin/env python3
"""Shipped RustRed Ordered step caches of the loop packs (Python stdlib only).

Each loop pack may carry `ordered-cache/<label>/`, one RustRed Ordered step-cache
directory per reduction program (`ordered-step-cache.txt` and `shards/*.rrstep`,
exactly as `rustred::reduction::OrderedStepCache::save` writes them), described by
`ordered-cache.json` and the loop manifest section
`"ordered_cache": {"path": "ordered-cache", "metadata": "ordered-cache.json"}`.

Vakint produces them with its `ordered_cache_maintenance` example (`prepare`, then
`stage` here) and verifies them again when it installs them: SHA-256 against the
loop manifest, BLAKE3 stamps and payload digests in RustRed, and the engine binding
(the producing engine or a verified restamp attestation). This module checks what
can be checked without BLAKE3: inventory, sizes, manifest structure, shard headers
and the agreement of metadata, RustRed manifests and files.

Commands:
  stage --export DIR      install the caches exported by `ordered_cache_maintenance
                          prepare` (replaces the ordered caches of those loop counts)
  remove-dfs              remove the depth-first (DFS) prepared caches of every pack
  validate                validate every pack's ordered caches
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from data import (  # noqa: E402 - the tools directory is not a package
    ROOT,
    checked_path,
    digest,
    file_record,
    read_json,
    write_json,
)

SCHEMA = "vakint.external-data.ordered-cache.v1"
SECTION = {"path": "ordered-cache", "metadata": "ordered-cache.json"}
RUSTRED_MANIFEST = "ordered-step-cache.txt"
RUSTRED_CACHE_SCHEMA = "rustred.ordered-step-cache.v2"
SHARD_MAGIC = b"RR-ORDERED-STEP1"
SHARD_HEADER = 16 + 32 + 1 + 2 + 8 + 8 + 32
# GitHub refuses files above 100 MiB; stay clearly below for every shard.
SHARD_FILE_BYTES_LIMIT = 95_000_000
LABEL = re.compile(r"[1-5]L-[a-z0-9][a-z0-9-]{0,63}")
HEX64 = re.compile(r"[0-9a-f]{64}")
DESCRIPTION_KEYS = (
    "schema",
    "semantics",
    "engine",
    "adapter",
    "family",
    "program",
    "variables",
    "unresolved",
    "terminals",
)
STAGES = {"integral": 0, "route": 1, "apply": 2}
PROGRAM_KEYS = {
    "label", "path", "adapter", "stamp", "content_blake3", "records", "shards",
    "bytes", "engine", "description",
}


def parse_rustred_manifest(text):
    """Return (description, stamp, shard rows) of an `ordered-step-cache.txt`."""
    lines = text.split("\n")
    if lines[-1] != "":
        raise ValueError("RustRed cache manifest must end with a newline")
    lines = lines[:-1]
    if len(lines) < len(DESCRIPTION_KEYS) + 2 or lines[-1] != "end":
        raise ValueError("truncated RustRed cache manifest")
    head = lines[: len(DESCRIPTION_KEYS)]
    for key, line in zip(DESCRIPTION_KEYS, head, strict=True):
        if not line.startswith(key + " "):
            raise ValueError(f"RustRed cache manifest line {key!r} missing")
    description = "".join(line + "\n" for line in head)
    stamp_line = lines[len(DESCRIPTION_KEYS)]
    if not stamp_line.startswith("stamp ") or not HEX64.fullmatch(stamp_line[6:]):
        raise ValueError("invalid RustRed cache stamp")
    shards = []
    for line in lines[len(DESCRIPTION_KEYS) + 1 : -1]:
        fields = line.split(" ")
        if len(fields) != 8 or fields[0] != "shard" or fields[1] not in STAGES:
            raise ValueError(f"invalid RustRed shard line {line!r}")
        _, stage, support, klass, name, records, size, payload = fields
        if (
            not re.fullmatch(r"shards/[A-Za-z0-9_-][A-Za-z0-9._-]*\.rrstep", name)
            or not re.fullmatch(r"[0-9]+", support)
            or not re.fullmatch(r"[0-9a-f]{16}", klass)
            or not re.fullmatch(r"[0-9]+", records)
            or not re.fullmatch(r"[0-9]+", size)
            or not HEX64.fullmatch(payload)
        ):
            raise ValueError(f"invalid RustRed shard line {line!r}")
        shards.append({
            "stage": stage,
            "support": int(support),
            "class": int(klass, 16),
            "file": name,
            "records": int(records),
            "bytes": int(size),
            "payload_blake3": payload,
        })
    if len({row["file"] for row in shards}) != len(shards):
        raise ValueError("RustRed cache manifest repeats a shard file")
    return description, stamp_line[6:], shards


def check_shard(path, stamp, row):
    """Header checks of one shard file (the payload BLAKE3 is RustRed's)."""
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"missing ordered cache shard {path}")
    size = path.stat().st_size
    if size != row["bytes"] or size < SHARD_HEADER:
        raise ValueError(f"ordered cache shard size differs from its manifest: {path}")
    if size > SHARD_FILE_BYTES_LIMIT:
        raise ValueError(f"ordered cache shard exceeds {SHARD_FILE_BYTES_LIMIT} bytes: {path}")
    with path.open("rb") as stream:
        header = stream.read(SHARD_HEADER)
    if (
        header[:16] != SHARD_MAGIC
        or header[16:48] != bytes.fromhex(stamp)
        or header[48] != STAGES[row["stage"]]
        or int.from_bytes(header[49:51], "little") != row["support"]
        or int.from_bytes(header[51:59], "little") != row["class"]
        or int.from_bytes(header[59:67], "little") != size - SHARD_HEADER
        or header[67:99] != bytes.fromhex(row["payload_blake3"])
    ):
        raise ValueError(f"ordered cache shard header differs from its manifest: {path}")


def program_files(directory, program):
    """Relative loop-pack paths of one program cache, checked against metadata."""
    label = program["label"]
    base = checked_path(directory, program["path"])
    text = (base / RUSTRED_MANIFEST).read_text()
    description, stamp, shards = parse_rustred_manifest(text)
    lines = dict(line.split(" ", 1) for line in description.splitlines())
    if lines["schema"] != RUSTRED_CACHE_SCHEMA:
        raise ValueError(f"{label}: unsupported RustRed cache schema {lines['schema']}")
    if (
        program["stamp"] != stamp
        or program["description"] != description
        or program["engine"] != lines["engine"]
        or program["adapter"] != lines["adapter"]
        or program["records"] != sum(row["records"] for row in shards)
        or program["bytes"] != sum(row["bytes"] for row in shards)
        or program["shards"] != len(shards)
    ):
        raise ValueError(f"{label}: ordered cache metadata differs from its RustRed manifest")
    for row in shards:
        check_shard(checked_path(base, row["file"]), stamp, row)
    files = {f"{program['path']}/{RUSTRED_MANIFEST}"}
    files.update(f"{program['path']}/{row['file']}" for row in shards)
    return files


def check_metadata(metadata, loop_count):
    if (
        not isinstance(metadata, dict)
        or metadata.get("schema") != SCHEMA
        or metadata.get("loop_count") != loop_count
        or not isinstance(metadata.get("programs"), list)
        or not metadata["programs"]
        or not isinstance(metadata.get("workload"), list)
        or not isinstance(metadata.get("producer"), dict)
    ):
        raise ValueError(f"invalid {loop_count}L ordered cache metadata")
    labels = set()
    for program in metadata["programs"]:
        if not isinstance(program, dict) or set(program) != PROGRAM_KEYS:
            raise ValueError("invalid ordered cache program fields")
        label = program["label"]
        if (
            not isinstance(label, str)
            or not LABEL.fullmatch(label)
            or not label.startswith(f"{loop_count}L-")
            or label in labels
            or program["path"] != f"{SECTION['path']}/{label}"
            or not isinstance(program["stamp"], str)
            or not HEX64.fullmatch(program["stamp"])
            or not isinstance(program["content_blake3"], str)
            or not HEX64.fullmatch(program["content_blake3"])
        ):
            raise ValueError(f"invalid ordered cache program {label!r}")
        for key in ("records", "shards", "bytes"):
            if type(program[key]) is not int or program[key] < 0:
                raise ValueError(f"invalid ordered cache {key} of {label}")
        labels.add(label)


def validate_loop(directory, loop):
    """Validate one loop pack's ordered caches; returns the number of programs."""
    directory = Path(directory)
    section = loop.get("ordered_cache")
    present = {name for name in loop["files"] if name.startswith(SECTION["path"] + "/")}
    if section is None:
        if present or SECTION["metadata"] in loop["files"]:
            raise ValueError("ordered cache files without an ordered_cache section")
        return 0
    if section != SECTION:
        raise ValueError(f"unsupported ordered_cache section {section!r}")
    if SECTION["metadata"] not in loop["files"]:
        raise ValueError("ordered cache metadata is not listed in the loop manifest")
    metadata = read_json(checked_path(directory, SECTION["metadata"]))
    check_metadata(metadata, loop["loop_count"])
    expected = set()
    for program in metadata["programs"]:
        expected |= program_files(directory, program)
    if expected != present:
        raise ValueError(f"{loop['loop_count']}L ordered cache inventory differs from its metadata")
    return len(metadata["programs"])


def update_root_manifest(root, loop_count, loop_path):
    manifest_path = root / "manifest.json"
    manifest = read_json(manifest_path)
    (pack,) = [pack for pack in manifest["loop_packs"] if pack["loop_count"] == loop_count]
    pack["manifest_sha256"] = digest(loop_path)
    write_json(manifest_path, manifest)


RETIREMENT_RECEIPT = "provenance/retired-dfs-caches-v1/receipt.json"
RETIREMENT_SCHEMA = "vakint.external-data.retired-dfs-caches.v1"


def retired_dfs_files(root=ROOT):
    """{path: {sha256, bytes}} of the retired depth-first cache files."""
    path = Path(root) / RETIREMENT_RECEIPT
    if not path.exists():
        return {}
    receipt = read_json(path)
    if receipt.get("schema") != RETIREMENT_SCHEMA or not isinstance(receipt.get("files"), list):
        raise ValueError("invalid retired DFS cache receipt")
    files = {}
    for item in receipt["files"]:
        if set(item) != {"path", "sha256", "bytes"} or item["path"] in files:
            raise ValueError("invalid retired DFS cache receipt row")
        files[item["path"]] = {"sha256": item["sha256"], "bytes": item["bytes"]}
    return files


def remove_dfs(root=ROOT, *, source_commit=None):
    """Retire the depth-first prepared caches (`cache/`, cache metadata) of every pack.

    Every removed file and every removed manifest section is recorded in
    `provenance/retired-dfs-caches-v1/receipt.json`; the files stay available
    in Git history and the migration receipt keeps validating against it.
    """
    root = Path(root)
    receipt_path = root / RETIREMENT_RECEIPT
    if receipt_path.exists():
        raise ValueError("depth-first caches were already retired")
    receipt = {
        "schema": RETIREMENT_SCHEMA,
        "reason": (
            "Vakint reduces only with RustRed's ordered scheduler since the removal of "
            "depth-first reduction; it never reads these depth-first completed-result "
            "caches. Ordered step caches replace them (ordered-cache/)."
        ),
        "last_source_commit": source_commit,
        "removed_manifest_sections": {},
        "files": [],
    }
    for loop_path in sorted(root.glob("[1-5]L/manifest.json")):
        loop = read_json(loop_path)
        directory = loop_path.parent
        cache = loop.get("cache", {"available": False})
        names = [name for name in loop["files"] if name.startswith("cache/")]
        metadata = cache.get("metadata")
        if metadata:
            names.append(metadata)
        if not names and not cache.get("available"):
            continue
        prefix = f"{loop['loop_count']}L"
        for name in sorted(names):
            path = checked_path(directory, name)
            record = file_record(path)
            if record != loop["files"][name]:
                raise ValueError(f"{prefix}/{name} differs from its loop manifest")
            receipt["files"].append({"path": f"{prefix}/{name}", **record})
            path.unlink()
            del loop["files"][name]
        if (directory / "cache").exists():
            if any(path.is_file() for path in (directory / "cache").rglob("*")):
                raise ValueError(f"unlisted files remain in {directory / 'cache'}")
            shutil.rmtree(directory / "cache")
        removed = {"cache": cache}
        revision = loop.get("provenance", {}).pop("native_cache_rustred_revision", None)
        if revision is not None:
            removed["provenance.native_cache_rustred_revision"] = revision
        receipt["removed_manifest_sections"][prefix] = removed
        loop["cache"] = {"available": False}
        write_json(loop_path, loop)
        update_root_manifest(root, loop["loop_count"], loop_path)
    write_json(receipt_path, receipt)
    return {
        loop: sum(1 for item in receipt["files"] if item["path"].startswith(loop + "/"))
        for loop in receipt["removed_manifest_sections"]
    }


def stage(export, root=ROOT):
    """Install `EXPORT/<L>L/ordered-cache{,.json}` into the packs of this checkout."""
    export, root = Path(export).resolve(), Path(root)
    if export.is_relative_to(root.resolve()):
        raise ValueError("stage from an export directory outside the repository")
    staged = {}
    for exported in sorted(export.glob("[1-5]L/" + SECTION["metadata"])):
        loop_count = int(exported.parent.name[:-1])
        source = exported.parent
        metadata = read_json(exported)
        check_metadata(metadata, loop_count)
        files = set()
        for program in metadata["programs"]:
            files |= program_files(source, program)
        found = {
            path.relative_to(source).as_posix()
            for path in (source / SECTION["path"]).rglob("*")
            if path.is_file()
        }
        if found != files:
            raise ValueError(f"{loop_count}L export inventory differs from its metadata")
        loop_path = root / f"{loop_count}L/manifest.json"
        loop = read_json(loop_path)
        directory = loop_path.parent
        for name in [n for n in loop["files"] if n.startswith(SECTION["path"] + "/")]:
            del loop["files"][name]
        loop["files"].pop(SECTION["metadata"], None)
        if (directory / SECTION["path"]).exists():
            shutil.rmtree(directory / SECTION["path"])
        for name in sorted(files) + [SECTION["metadata"]]:
            target = checked_path(directory, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / name, target)
            loop["files"][name] = file_record(target)
            if loop["files"][name] != file_record(source / name):
                raise ValueError(f"copy of {name} differs from the export")
        loop["files"] = dict(sorted(loop["files"].items()))
        loop["ordered_cache"] = dict(SECTION)
        validate_loop(directory, loop)
        write_json(loop_path, loop)
        update_root_manifest(root, loop_count, loop_path)
        staged[f"{loop_count}L"] = {
            "programs": len(metadata["programs"]),
            "files": len(files) + 1,
            "bytes": sum(program["bytes"] for program in metadata["programs"]),
        }
    if not staged:
        raise ValueError(f"no <L>L/{SECTION['metadata']} in {export}")
    return staged


def validate(root=ROOT):
    root = Path(root)
    result = {}
    for pack in read_json(root / "manifest.json")["loop_packs"]:
        path = checked_path(root, pack["manifest"])
        result[f"{pack['loop_count']}L"] = validate_loop(path.parent, read_json(path))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    staging = commands.add_parser("stage")
    staging.add_argument("--export", type=Path, required=True)
    removal = commands.add_parser("remove-dfs")
    removal.add_argument("--source-commit", required=True,
                         help="last source commit that still contains the depth-first caches")
    commands.add_parser("validate")
    args = parser.parse_args()
    import json

    if args.command == "stage":
        print(json.dumps(stage(args.export)))
    elif args.command == "remove-dfs":
        print(json.dumps(remove_dfs(source_commit=args.source_commit)))
    else:
        print(json.dumps(validate()))


if __name__ == "__main__":
    main()
