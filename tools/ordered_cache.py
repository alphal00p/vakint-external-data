#!/usr/bin/env python3
"""Shipped RustRed Ordered step caches of the loop packs (Python stdlib only).

A loop pack may ship one RustRed Ordered step-cache directory per reduction
program, named as in a Vakint cache directory:

    <L>L/ordered-cache/<label>.<tables16>.<stamp16>/ordered-step-cache.txt
    <L>L/ordered-cache/<label>.<tables16>.<stamp16>/shards/*.rrstep
    <L>L/ordered-cache/<label>.<tables16>.<stamp16>/ordered-tail.rrtail   (optional)
    <L>L/ordered-cache.json                     (schema vakint.external-data.ordered-cache.v2)

and the loop manifest section
`"ordered_cache": {"path": "ordered-cache", "metadata": "ordered-cache.json"}`.
Every file is listed in the loop manifest's `files` (sha256, bytes) like any payload.

Caches are bound by versioning only: the RustRed step-cache schema
(`rustred.ordered-step-cache.v3`), the hand-bumped step semantics and cheap identity
fields of the program make the stamp; Vakint uses a shipped cache iff its stamp
equals the running build's, its directory carries the program's rule tables and its
files match the manifest sha256, and otherwise runs that program cold. `tables16` is
the start of the program's rule-table identity, recomputed here from the pack exactly
as Vakint does (`program_rule_tables`). This module checks everything that needs no
BLAKE3: names, rule tables, inventory, sizes, RustRed manifest structure and version
lines, shard headers, tail-table headers, metadata, and the per-file limit. Stamps and
payload digests are BLAKE3 and are checked by RustRed when Vakint opens a cache.

Commands:
  stage --cache-dir DIR [--metadata JSON] [--loops L ...] [--link]
                          stage program directories of a Vakint cache directory
                          (as `ordered_cache_maintenance prepare` writes them)
  stage --export DIR [--loops L ...] [--link]
                          stage an export shaped like the packs
                          (DIR/<L>L/ordered-cache.json + DIR/<L>L/ordered-cache/<dir>/)
  remove --loops L ...    remove the shipped Ordered caches of these loop counts
  receipt --program DIR --artifacts ROOT --output FILE [--metadata JSON]
                          receipt of a cache kept outside the repository (full 5L quadratic)
  light-bytes             bytes of the 5L release budget (see `light_bytes`)
  remove-dfs              retire the depth-first (DFS) prepared caches of every pack
  validate                validate every pack's Ordered caches
Staging replaces the Ordered caches of the staged loop counts, never touches another
file of the pack, and refreshes the root manifest's `manifest_sha256`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
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

SCHEMA = "vakint.external-data.ordered-cache.v2"
SECTION = {"path": "ordered-cache", "metadata": "ordered-cache.json"}
RUSTRED_MANIFEST = "ordered-step-cache.txt"
RUSTRED_CACHE_SCHEMA = "rustred.ordered-step-cache.v3"
SHARD_MAGIC = b"RR-ORDERED-STEP1"
SHARD_HEADER = 16 + 32 + 1 + 2 + 8 + 8 + 32
TAIL_FILE = "ordered-tail.rrtail"
TAIL_MAGIC = b"RR-ORDERED-TAIL2"
TAIL_SCHEMA = "rustred.ordered-tail.v3"
# Every shipped cache file, and the 5L release budget (`light_bytes`): GitHub refuses
# files above 100 MiB; the decimal boundary is the one of the former 5L LIGHT cache.
FILE_BYTES_LIMIT = 95_000_000
DESCRIPTION_KEYS = ("schema", "semantics", "adapter", "family", "variables", "unresolved")
STAGES = {"integral": 0, "route": 1, "apply": 2}
# RustRed `OrderedStepCacheAdapter::as_str` and its Debug name in tail-table headers.
ADAPTERS = {
    "closed-artifact": "ClosedArtifact",
    "candidate-program": "CandidateProgram",
    "saved-application": "SavedApplication",
}
LABEL = re.compile(r"[1-5]L-[a-z0-9][a-z0-9-]{0,63}")
DIRECTORY = re.compile(r"(?P<label>[1-5]L-[a-z0-9][a-z0-9-]{0,63})\.(?P<tables>[0-9a-f]{16})\.(?P<stamp>[0-9a-f]{16})")
HEX64 = re.compile(r"[0-9a-f]{64}")
PROGRAM_KEYS = {
    "label", "directory", "rule_tables", "stamp", "adapter", "records", "shards", "bytes",
    "tail_bytes", "complete", "trim",
}
RECEIPT_SCHEMA = "vakint.external-data.ordered-cache-receipt.v1"
TRIM_KEYS = {"from_records", "from_shards", "from_bytes", "from_tail_bytes", "method", "full_cache"}
# Optional: the complete zero-momentum cache a trimmed 5L cache extends (release budget).
TRIM_BASE_KEYS = ("base_bytes", "base_tail_bytes")
# Vakint's closed programs (`artifact.rs` shipped_family_for_loop_count) and four-loop
# candidate programs (`four_loop.rs`); the five-loop label follows the saved application.
CLOSED_LABELS = {1: "1L-unit-mass-vacuum-k1", 2: "2L-unit-mass-vacuum-k3", 3: "3L-unit-mass-vacuum-k6"}
FOUR_LOOP_PROGRAMS = {"4L-four-loop-h": "h", "4L-four-loop-fg": "fg", "4L-four-loop-bmw": "bmw",
                      "4L-four-loop-x": "x"}
FOUR_LOOP_INPUTS = ("csv", "candidates.rrbin.gz", "rrcat.bin.gz", "rrnorm.bin")


# ---------------------------------------------------------------------------
# Program identities (Vakint `rustred_evaluation::cache`)


def _field(state, data):
    state.update(struct.pack("<Q", len(data)))
    state.update(data)


def declared_rule_tables(files):
    """Vakint `declared_rule_tables`: (path, declared sha256) pairs in order."""
    state = hashlib.sha256(b"vakint-ordered-cache-rule-tables-v1\0")
    for path, sha256 in files:
        _field(state, path.encode())
        _field(state, sha256.encode())
    return state.hexdigest()


def saved_application_identity(application, loop):
    """Vakint `saved_application_digest` of a five-loop pack's `ibps/application.json`."""
    state = hashlib.sha256(b"vakint-saved-application-cache-v1\0")
    _field(state, application)
    _field(state, loop["dimension"].encode())
    _field(state, loop["normalization"].encode())
    families = sorted(family["fingerprint"] for family in loop["families"])
    state.update(struct.pack("<Q", len(families)))
    for family in families:
        _field(state, family.encode())
    masters = sorted((master["family_sha256"], list(master["powers"])) for master in loop["masters"])
    state.update(struct.pack("<Q", len(masters)))
    for family, powers in masters:
        _field(state, family.encode())
        state.update(struct.pack("<Q", len(powers)))
        for power in powers:
            state.update(struct.pack("<q", power))
    return state.hexdigest()


def label_of(loop_count, name):
    """Vakint `OrderedCacheProgram::new` label of a family name."""
    safe = "".join(c.lower() if c.isascii() and (c.isalnum() or c in "-._") else "-"
                   for c in name.replace(".", "-").replace("_", "-"))[:64]
    return f"{loop_count}L-{safe}"


def program_rule_tables(directory, loop):
    """{label: rule tables hex} of every program Vakint loads from this pack.

    Reads only the pack's declared sha256 values (`data.py validate` checks them
    against the bytes) and, for five loops, `ibps/application.json`.
    """
    loop_count = loop["loop_count"]
    files = loop["files"]
    if loop_count in CLOSED_LABELS:
        record = files.get("ibps/rules.rrbin")
        return {CLOSED_LABELS[loop_count]: record["sha256"]} if record else {}
    if loop_count == 4:
        tables = {}
        for label, name in FOUR_LOOP_PROGRAMS.items():
            paths = [f"ibps/{name}.{extension}" for extension in FOUR_LOOP_INPUTS]
            if any(path in files for path in paths):
                tables[label] = declared_rule_tables(
                    (path, files[path]["sha256"]) for path in paths if path in files)
        return tables
    if loop_count == 5 and "ibps/application.json" in files:
        application = checked_path(Path(directory), "ibps/application.json").read_bytes()
        families = [family.get("name") for family in loop.get("families", [])]
        if len(families) != 1 or not isinstance(families[0], str):
            raise ValueError("five-loop pack must declare exactly one named saved-application family")
        return {label_of(5, families[0]): saved_application_identity(application, loop)}
    return {}


def directory_name(label, rule_tables, stamp):
    return f"{label}.{rule_tables[:16]}.{stamp[:16]}"


# ---------------------------------------------------------------------------
# RustRed files


def parse_rustred_manifest(text):
    """Return (description lines {key: value}, stamp, shard rows) of `ordered-step-cache.txt`."""
    lines = text.split("\n")
    if lines[-1] != "":
        raise ValueError("RustRed cache manifest must end with a newline")
    lines = lines[:-1]
    if len(lines) < len(DESCRIPTION_KEYS) + 2 or lines[-1] != "end":
        raise ValueError("truncated RustRed cache manifest")
    description = {}
    for key, line in zip(DESCRIPTION_KEYS, lines, strict=False):
        if not line.startswith(key + " "):
            raise ValueError(f"RustRed cache manifest line {key!r} missing")
        description[key] = line[len(key) + 1:]
    if description["schema"] != RUSTRED_CACHE_SCHEMA:
        raise ValueError(f"unsupported RustRed cache schema {description['schema']!r}")
    if description["adapter"] not in ADAPTERS:
        raise ValueError(f"unknown RustRed cache adapter {description['adapter']!r}")
    stamp_line = lines[len(DESCRIPTION_KEYS)]
    if not stamp_line.startswith("stamp ") or not HEX64.fullmatch(stamp_line[6:]):
        raise ValueError("invalid RustRed cache stamp")
    shards = []
    for line in lines[len(DESCRIPTION_KEYS) + 1: -1]:
        fields = line.split(" ")
        if len(fields) != 8 or fields[0] != "shard" or fields[1] not in STAGES:
            raise ValueError(f"invalid RustRed shard line {line!r}")
        _, stage, support, klass, name, records, size, payload = fields
        if (
            not re.fullmatch(r"shards/[A-Za-z0-9_-][A-Za-z0-9._-]*", name)
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
    if len({(row["stage"], row["support"], row["class"]) for row in shards}) != len(shards):
        raise ValueError("RustRed cache manifest repeats a shard")
    return description, stamp_line[6:], shards


def check_file_limit(path, limit=True):
    """Size of a cache file; with `limit`, at most FILE_BYTES_LIMIT (files in a pack)."""
    size = path.stat().st_size
    if limit and size > FILE_BYTES_LIMIT:
        raise ValueError(f"ordered cache file exceeds {FILE_BYTES_LIMIT} bytes: {path} ({size})")
    return size


def check_shard(path, stamp, row, limit=True):
    """Header checks of one shard file (the payload BLAKE3 is RustRed's)."""
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"missing ordered cache shard {path}")
    size = check_file_limit(path, limit)
    if size != row["bytes"] or size < SHARD_HEADER:
        raise ValueError(f"ordered cache shard size differs from its manifest: {path}")
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


def tail_header(path, limit=True):
    """{schema, semantics, adapter, bytes} of an `ordered-tail.rrtail` (payload BLAKE3 is RustRed's)."""
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"missing ordered tail table {path}")
    size = check_file_limit(path, limit)
    with path.open("rb") as stream:
        start = stream.read(24)
        if len(start) != 24 or start[:16] != TAIL_MAGIC:
            raise ValueError(f"not a RustRed {TAIL_SCHEMA} tail table: {path}")
        length = int.from_bytes(start[16:24], "little")
        if length > 1 << 20 or 24 + length + 40 > size:
            raise ValueError(f"truncated tail table header: {path}")
        identity = stream.read(length)
        payload = int.from_bytes(stream.read(8), "little")
    if 24 + length + 40 + payload != size:
        raise ValueError(f"tail table payload length differs from its header: {path}")
    try:
        lines = identity.decode().split("\n")
    except UnicodeDecodeError as error:
        raise ValueError(f"tail table header is not UTF-8: {path}") from error
    fields = dict(line.split(" ", 1) for line in lines if " " in line)
    if fields.get("schema") != TAIL_SCHEMA or "semantics" not in fields or "adapter" not in fields:
        raise ValueError(f"tail table header is not {TAIL_SCHEMA}: {path} ({fields.get('schema')!r})")
    return {"schema": fields["schema"], "semantics": fields["semantics"], "adapter": fields["adapter"],
            "bytes": size}


def inspect_program(base, name, limit=True):
    """Check one program directory `base/name`; returns its RustRed facts and file list.

    `limit`: every file at most FILE_BYTES_LIMIT (caches shipped in a pack).
    """
    match = DIRECTORY.fullmatch(name)
    if not match:
        raise ValueError(f"ordered cache directory {name!r} is not <label>.<tables16>.<stamp16>")
    directory = checked_path(Path(base), name)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError(f"missing ordered cache directory {directory}")
    manifest = directory / RUSTRED_MANIFEST
    if manifest.is_symlink() or not manifest.is_file():
        raise ValueError(f"{name}: no {RUSTRED_MANIFEST}")
    check_file_limit(manifest, limit)
    description, stamp, shards = parse_rustred_manifest(manifest.read_text())
    if stamp[:16] != match["stamp"]:
        raise ValueError(f"{name}: directory stamp differs from its RustRed manifest ({stamp[:16]})")
    for row in shards:
        check_shard(checked_path(directory, row["file"]), stamp, row, limit)
    files = [RUSTRED_MANIFEST] + [row["file"] for row in shards]
    tail = None
    if (directory / TAIL_FILE).exists() or (directory / TAIL_FILE).is_symlink():
        tail = tail_header(directory / TAIL_FILE, limit)
        if tail["adapter"] != ADAPTERS[description["adapter"]]:
            raise ValueError(f"{name}: tail table adapter {tail['adapter']} differs from the step cache's")
        files.append(TAIL_FILE)
    found = sorted(path.relative_to(directory).as_posix() for path in directory.rglob("*")
                   if path.is_file() or path.is_symlink())
    if found != sorted(files):
        extra, missing = sorted(set(found) - set(files))[:3], sorted(set(files) - set(found))[:3]
        raise ValueError(f"{name}: files differ from its RustRed manifest (extra {extra}, missing {missing})")
    return {
        "label": match["label"],
        "tables16": match["tables"],
        "stamp": stamp,
        "description": description,
        "adapter": description["adapter"],
        "records": sum(row["records"] for row in shards),
        "shards": len(shards),
        "bytes": sum(row["bytes"] for row in shards),
        "tail_bytes": tail["bytes"] if tail else 0,
        "tail": tail,
        "files": files,
    }


# ---------------------------------------------------------------------------
# Metadata


def check_trim(program):
    label = program["label"]
    if program["complete"]:
        if program["trim"] is not None:
            raise ValueError(f"{label}: a complete ordered cache has trim null")
        return
    trim = program["trim"]
    if not isinstance(trim, dict) or not TRIM_KEYS <= set(trim):
        raise ValueError(f"{label}: a trimmed ordered cache needs trim {sorted(TRIM_KEYS)}")
    for key in ("from_records", "from_shards", "from_bytes", "from_tail_bytes", *TRIM_BASE_KEYS):
        if key in trim and (type(trim[key]) is not int or trim[key] < 0):
            raise ValueError(f"{label}: invalid trim {key}")
    if not isinstance(trim["method"], str) or not trim["method"] or not isinstance(trim["full_cache"], str):
        raise ValueError(f"{label}: trim method and full_cache must be text")
    if (trim["from_records"] < program["records"] or trim["from_bytes"] < program["bytes"]
            or trim["from_tail_bytes"] < program["tail_bytes"]):
        raise ValueError(f"{label}: a trimmed cache cannot exceed the cache it was trimmed from")
    if trim.get("base_bytes", 0) > program["bytes"] or trim.get("base_tail_bytes", 0) > program["tail_bytes"]:
        raise ValueError(f"{label}: the declared base exceeds the trimmed cache")


def check_program_entry(program, loop_count, prefix=SECTION["path"] + "/"):
    if not isinstance(program, dict) or not PROGRAM_KEYS <= set(program):
        raise ValueError(f"ordered cache program needs the fields {sorted(PROGRAM_KEYS)}")
    label = program["label"]
    if (
        not isinstance(label, str)
        or not LABEL.fullmatch(label)
        or not label.startswith(f"{loop_count}L-")
        or not isinstance(program["rule_tables"], str)
        or not HEX64.fullmatch(program["rule_tables"])
        or not isinstance(program["stamp"], str)
        or not HEX64.fullmatch(program["stamp"])
        or program["directory"] != prefix + directory_name(label, program["rule_tables"], program["stamp"])
        or program["adapter"] not in ADAPTERS
        or type(program["complete"]) is not bool
    ):
        raise ValueError(f"invalid ordered cache program {label!r}")
    for key in ("records", "shards", "bytes", "tail_bytes"):
        if type(program[key]) is not int or program[key] < 0:
            raise ValueError(f"invalid ordered cache {key} of {label}")
    check_trim(program)


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
    labels = []
    for program in metadata["programs"]:
        check_program_entry(program, loop_count)
        labels.append(program["label"])
    if labels != sorted(set(labels)):
        raise ValueError(f"{loop_count}L ordered cache programs must be unique and sorted by label")


def agree(program, facts, tables, producer=None):
    """Agreement of one `programs[]` entry, its checked files and the pack's rule tables.

    When the producer names RustRed's version constants
    (`producer.rustred.{ordered_step_cache_schema, ordered_step_semantics,
    ordered_tail_schema, ordered_tail_semantics}`), the files must carry them.
    """
    label = program["label"]
    if label not in tables:
        raise ValueError(f"{label}: this pack loads no program with that label "
                         f"(programs: {sorted(tables)})")
    if program["rule_tables"] != tables[label]:
        raise ValueError(f"{label}: ordered cache was prepared for other rule tables "
                         f"({program['rule_tables'][:16]}, this pack has {tables[label][:16]})")
    for key in ("stamp", "adapter", "records", "shards", "bytes", "tail_bytes"):
        if program[key] != facts[key]:
            raise ValueError(f"{label}: ordered cache metadata {key} differs from its files")
    rustred = (producer or {}).get("rustred")
    if isinstance(rustred, dict):
        tail = facts["tail"] or {}
        for key, value in (
            ("ordered_step_cache_schema", facts["description"]["schema"]),
            ("ordered_step_semantics", facts["description"]["semantics"]),
            ("ordered_tail_schema", tail.get("schema")),
            ("ordered_tail_semantics", tail.get("semantics")),
        ):
            if key in rustred and value is not None and rustred[key] != value:
                raise ValueError(f"{label}: files carry {value!r}, the producer declares {key} {rustred[key]!r}")


def check_program(directory, program, tables, producer=None):
    """Check one staged program; returns its pack-relative file paths."""
    base = checked_path(Path(directory), SECTION["path"])
    facts = inspect_program(base, program["directory"].split("/", 1)[1])
    agree(program, facts, tables, producer)
    return {f"{program['directory']}/{name}" for name in facts["files"]}


def validate_loop(directory, loop):
    """Validate one loop pack's Ordered caches; returns the number of programs."""
    directory = Path(directory)
    section = loop.get("ordered_cache")
    present = {name for name in loop["files"] if name.startswith(SECTION["path"] + "/")}
    if section is None:
        if present or SECTION["metadata"] in loop["files"] or (directory / SECTION["path"]).exists():
            raise ValueError(f"{loop['loop_count']}L: ordered cache files without an ordered_cache section")
        return 0
    if section != SECTION:
        raise ValueError(f"unsupported ordered_cache section {section!r}")
    if SECTION["metadata"] not in loop["files"]:
        raise ValueError("ordered cache metadata is not listed in the loop manifest")
    metadata = read_json(checked_path(directory, SECTION["metadata"]))
    check_metadata(metadata, loop["loop_count"])
    tables = program_rule_tables(directory, loop)
    expected = set()
    for program in metadata["programs"]:
        expected |= check_program(directory, program, tables, metadata["producer"])
    if expected != present:
        raise ValueError(f"{loop['loop_count']}L ordered cache inventory differs from its metadata")
    for name in expected | {SECTION["metadata"]}:
        if file_record(checked_path(directory, name)) != loop["files"][name]:
            raise ValueError(f"{loop['loop_count']}L ordered cache file differs from the loop manifest: {name}")
    return len(metadata["programs"])


def light_bytes(directory, loop):
    """Bytes a five-loop pack's shipped Ordered caches count against the release budget.

    Every program counts with its shard and tail bytes; a trimmed program
    (`complete: false`) counts only beyond the complete zero-momentum cache it
    extends when its `trim` declares that base (`base_bytes`, `base_tail_bytes`),
    i.e. its quadratic increment (shipped-cache-format.md section 5).
    """
    if loop.get("ordered_cache") is None:
        return 0
    metadata = read_json(checked_path(Path(directory), loop["ordered_cache"]["metadata"]))
    total = 0
    for program in metadata["programs"]:
        size = program["bytes"] + program["tail_bytes"]
        if not program["complete"]:
            size -= sum(program["trim"].get(key, 0) for key in TRIM_BASE_KEYS)
        total += size
    return total


# ---------------------------------------------------------------------------
# Staging


def update_root_manifest(root, loop_count, loop_path):
    manifest_path = root / "manifest.json"
    manifest = read_json(manifest_path)
    (pack,) = [pack for pack in manifest["loop_packs"] if pack["loop_count"] == loop_count]
    pack["manifest_sha256"] = digest(loop_path)
    write_json(manifest_path, manifest)


def with_section(loop):
    """The loop manifest with the ordered_cache section right after `cache`."""
    items = [(key, value) for key, value in loop.items() if key != "ordered_cache"]
    keys = [key for key, _ in items]
    index = keys.index("cache") + 1 if "cache" in keys else keys.index("files")
    items.insert(index, ("ordered_cache", dict(SECTION)))
    return dict(items)


def place(source, target, link):
    target.parent.mkdir(parents=True, exist_ok=True)
    if link:
        try:
            os.link(source, target)
            return
        except OSError:
            pass
    shutil.copyfile(source, target)


def remove_loop(root, loop_count):
    """Remove the shipped Ordered caches of one pack (files, metadata, section)."""
    loop_path = Path(root) / f"{loop_count}L/manifest.json"
    loop = read_json(loop_path)
    directory = loop_path.parent
    for name in [n for n in loop["files"] if n.startswith(SECTION["path"] + "/")]:
        del loop["files"][name]
    loop["files"].pop(SECTION["metadata"], None)
    loop.pop("ordered_cache", None)
    if (directory / SECTION["path"]).exists():
        shutil.rmtree(directory / SECTION["path"])
    if (directory / SECTION["metadata"]).exists():
        (directory / SECTION["metadata"]).unlink()
    loop["files"] = dict(sorted(loop["files"].items()))
    write_json(loop_path, loop)
    update_root_manifest(Path(root), loop_count, loop_path)
    return loop


def install(root, loop_count, metadata, sources, *, link=False):
    """Install checked program directories `sources` {directory name: path} with `metadata`."""
    root = Path(root)
    loop_path = root / f"{loop_count}L/manifest.json"
    directory = loop_path.parent
    check_metadata(metadata, loop_count)
    tables = program_rule_tables(directory, read_json(loop_path))
    staged = []
    for program in metadata["programs"]:
        name = program["directory"].split("/", 1)[1]
        facts = inspect_program(sources[name].parent, name)
        agree(program, facts, tables, metadata["producer"])
        staged.append((program, sources[name], facts))
    loop = remove_loop(root, loop_count)
    for program, source, facts in staged:
        for name in facts["files"]:
            target = checked_path(directory, f"{program['directory']}/{name}")
            place(source / name, target, link)
            record = file_record(target)
            if record != file_record(source / name):
                raise ValueError(f"copy of {program['directory']}/{name} differs from its source")
            loop["files"][f"{program['directory']}/{name}"] = record
    write_json(directory / SECTION["metadata"], metadata)
    loop["files"][SECTION["metadata"]] = file_record(directory / SECTION["metadata"])
    loop["files"] = dict(sorted(loop["files"].items()))
    loop = with_section(loop)
    validate_loop(directory, loop)
    write_json(loop_path, loop)
    update_root_manifest(root, loop_count, loop_path)
    return {
        "programs": [program["directory"] for program, _, _ in staged],
        "records": sum(program["records"] for program, _, _ in staged),
        "files": sum(len(facts["files"]) for _, _, facts in staged) + 1,
        "bytes": sum(program["bytes"] + program["tail_bytes"] for program, _, _ in staged),
    }


def program_entry(facts, rule_tables, overrides=None):
    """A `programs[]` entry of checked program facts; `overrides` adds complete/trim/extras."""
    overrides = dict(overrides or {})
    entry = {
        "label": facts["label"],
        "directory": f"{SECTION['path']}/{directory_name(facts['label'], rule_tables, facts['stamp'])}",
        "rule_tables": rule_tables,
        "stamp": facts["stamp"],
        "adapter": facts["adapter"],
        "records": facts["records"],
        "shards": facts["shards"],
        "bytes": facts["bytes"],
        "tail_bytes": facts["tail_bytes"],
        "complete": overrides.pop("complete", True),
        "trim": overrides.pop("trim", None),
    }
    for key in PROGRAM_KEYS & set(overrides):
        raise ValueError(f"{facts['label']}: metadata cannot override {key}")
    entry.update(overrides)
    return entry


def stage_cache_dir(cache_dir, root=ROOT, *, metadata=None, loops=None, link=False):
    """Stage program directories `<label>.<tables16>.<stamp16>` of a Vakint cache directory.

    `metadata` (optional): {"producer": {...}, "workload": [{..., "loop_count": L}, ...],
    "programs": {label: {"complete": false, "trim": {...}, ...}}}; workload rows go to
    the pack of their `loop_count` (rows without it to every staged pack).
    """
    cache_dir, root = Path(cache_dir).resolve(), Path(root)
    if cache_dir.is_relative_to(root.resolve()):
        raise ValueError("stage from a cache directory outside the repository")
    metadata = metadata or {}
    overrides = metadata.get("programs", {})
    by_loop = {}
    for path in sorted(cache_dir.iterdir()):
        match = DIRECTORY.fullmatch(path.name)
        if not match or not path.is_dir():
            continue
        loop_count = int(match["label"][0])
        if loops is not None and loop_count not in loops:
            continue
        by_loop.setdefault(loop_count, []).append(path)
    if loops is not None and set(loops) - set(by_loop):
        raise ValueError(f"no program directory for {sorted(set(loops) - set(by_loop))}L in {cache_dir}")
    if not by_loop:
        raise ValueError(f"no <label>.<tables16>.<stamp16> program directory in {cache_dir}")
    unknown = set(overrides) - {DIRECTORY.fullmatch(p.name)["label"] for ps in by_loop.values() for p in ps}
    if unknown:
        raise ValueError(f"metadata names programs that are not staged: {sorted(unknown)}")
    documents = {}
    for loop_count, paths in sorted(by_loop.items()):
        loop = read_json(root / f"{loop_count}L/manifest.json")
        tables = program_rule_tables(root / f"{loop_count}L", loop)
        programs, sources = [], {}
        for path in paths:
            facts = inspect_program(path.parent, path.name)
            label = facts["label"]
            if label not in tables:
                raise ValueError(f"{path.name}: the {loop_count}L pack loads no program {label}")
            if facts["tables16"] != tables[label][:16]:
                raise ValueError(f"{path.name}: prepared for other rule tables than the {loop_count}L pack's "
                                 f"({tables[label][:16]})")
            if label in {program["label"] for program in programs}:
                raise ValueError(f"{loop_count}L: several caches of program {label}")
            programs.append(program_entry(facts, tables[label], overrides.get(label)))
            sources[path.name] = path
        programs.sort(key=lambda program: program["label"])
        document = {
            "schema": SCHEMA,
            "loop_count": loop_count,
            "producer": metadata.get("producer", {}),
            "workload": [row for row in metadata.get("workload", [])
                         if row.get("loop_count", loop_count) == loop_count],
            "programs": programs,
        }
        documents[loop_count] = (document, sources)
    # Every pack's caches are checked above before any pack is changed.
    return {f"{loop_count}L": install(root, loop_count, document, sources, link=link)
            for loop_count, (document, sources) in documents.items()}


def stage_export(export, root=ROOT, *, loops=None, link=False):
    """Stage `EXPORT/<L>L/ordered-cache.json` with `EXPORT/<L>L/ordered-cache/<dir>/`."""
    export, root = Path(export).resolve(), Path(root)
    if export.is_relative_to(root.resolve()):
        raise ValueError("stage from an export directory outside the repository")
    staged = {}
    for exported in sorted(export.glob("[1-5]L/" + SECTION["metadata"])):
        loop_count = int(exported.parent.name[:-1])
        if loops is not None and loop_count not in loops:
            continue
        metadata = read_json(exported)
        check_metadata(metadata, loop_count)
        base = exported.parent / SECTION["path"]
        names = {program["directory"].split("/", 1)[1] for program in metadata["programs"]}
        found = {path.name for path in base.iterdir()} if base.is_dir() else set()
        if found != names:
            raise ValueError(f"{loop_count}L export holds other program directories than its metadata")
        staged[f"{loop_count}L"] = install(root, loop_count, metadata, {name: base / name for name in names},
                                           link=link)
    if not staged:
        raise ValueError(f"no <L>L/{SECTION['metadata']} in {export}")
    return staged


def receipt(program, artifacts, *, metadata=None):
    """Receipt of a program cache kept outside the repository (e.g. the full 5L quadratic cache).

    Same fields as a `programs[]` entry (directory = the bare directory name, to be placed
    inside a Vakint cache directory) plus `files` {relative path: {sha256, bytes}}; the rule
    tables are recomputed from the pack of `artifacts` the cache was prepared for.
    """
    program, artifacts = Path(program), Path(artifacts)
    facts = inspect_program(program.parent, program.name, limit=False)
    loop_count = int(facts["label"][0])
    tables = program_rule_tables(artifacts / f"{loop_count}L", read_json(artifacts / f"{loop_count}L/manifest.json"))
    if tables.get(facts["label"], "")[:16] != facts["tables16"]:
        raise ValueError(f"{program.name}: not prepared for the rule tables of {artifacts}")
    entry = program_entry(facts, tables[facts["label"]], (metadata or {}).get("program"))
    entry["directory"] = program.name
    entry["files"] = {name: file_record(program / name) for name in sorted(facts["files"])}
    document = {"schema": RECEIPT_SCHEMA, "loop_count": loop_count,
                "producer": (metadata or {}).get("producer", {}),
                "workload": (metadata or {}).get("workload", []),
                **entry}
    return document


# ---------------------------------------------------------------------------
# Retired depth-first caches


RETIREMENT_RECEIPT = "provenance/retired-dfs-caches-v1/receipt.json"
RETIREMENT_SCHEMA = "vakint.external-data.retired-dfs-caches.v1"


def retired_dfs_files(root=ROOT):
    """{path: {sha256, bytes}} of the retired depth-first cache files."""
    path = Path(root) / RETIREMENT_RECEIPT
    if not path.exists():
        return {}
    receipt_document = read_json(path)
    if receipt_document.get("schema") != RETIREMENT_SCHEMA or not isinstance(receipt_document.get("files"), list):
        raise ValueError("invalid retired DFS cache receipt")
    files = {}
    for item in receipt_document["files"]:
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
    document = {
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
            document["files"].append({"path": f"{prefix}/{name}", **record})
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
        document["removed_manifest_sections"][prefix] = removed
        loop["cache"] = {"available": False}
        write_json(loop_path, loop)
        update_root_manifest(root, loop["loop_count"], loop_path)
    write_json(receipt_path, document)
    return {
        loop: sum(1 for item in document["files"] if item["path"].startswith(loop + "/"))
        for loop in document["removed_manifest_sections"]
    }


# ---------------------------------------------------------------------------


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
    source = staging.add_mutually_exclusive_group(required=True)
    source.add_argument("--cache-dir", type=Path, help="Vakint cache directory (<label>.<tables16>.<stamp16>/)")
    source.add_argument("--export", type=Path, help="pack-shaped export (<L>L/ordered-cache{,.json})")
    staging.add_argument("--metadata", type=Path, help="producer/workload/programs JSON (--cache-dir only)")
    staging.add_argument("--loops", type=int, nargs="+", choices=range(1, 6))
    staging.add_argument("--link", action="store_true", help="hardlink instead of copying when possible")
    removal = commands.add_parser("remove")
    removal.add_argument("--loops", type=int, nargs="+", choices=range(1, 6), required=True)
    receipts = commands.add_parser("receipt")
    receipts.add_argument("--program", type=Path, required=True)
    receipts.add_argument("--artifacts", type=Path, required=True)
    receipts.add_argument("--output", type=Path, required=True)
    receipts.add_argument("--metadata", type=Path, help="JSON with producer, workload, program overrides")
    commands.add_parser("light-bytes")
    retirement = commands.add_parser("remove-dfs")
    retirement.add_argument("--source-commit", required=True,
                            help="last source commit that still contains the depth-first caches")
    commands.add_parser("validate")
    args = parser.parse_args()
    loops = set(args.loops) if getattr(args, "loops", None) else None
    if args.command == "stage":
        if args.export is not None:
            if args.metadata is not None:
                parser.error("--metadata is read from the export itself")
            result = stage_export(args.export, loops=loops, link=args.link)
        else:
            metadata = read_json(args.metadata) if args.metadata else None
            result = stage_cache_dir(args.cache_dir, metadata=metadata, loops=loops, link=args.link)
    elif args.command == "remove":
        for loop_count in sorted(loops):
            remove_loop(ROOT, loop_count)
        result = validate()
    elif args.command == "receipt":
        if args.output.exists():
            raise ValueError(f"refusing to replace {args.output}")
        metadata = read_json(args.metadata) if args.metadata else None
        result = receipt(args.program, args.artifacts, metadata=metadata)
        write_json(args.output, result)
        result = {"receipt": str(args.output), "directory": result["directory"], "files": len(result["files"])}
    elif args.command == "light-bytes":
        loop = read_json(ROOT / "5L/manifest.json")
        result = {"5L": light_bytes(ROOT / "5L", loop), "limit": FILE_BYTES_LIMIT}
    elif args.command == "remove-dfs":
        result = remove_dfs(source_commit=args.source_commit)
    else:
        result = validate()
    print(json.dumps(result))


if __name__ == "__main__":
    main()
