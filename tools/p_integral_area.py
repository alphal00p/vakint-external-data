#!/usr/bin/env python3
"""The top-level `p_integral/` area: Vakint's shipped p-integral data (Python stdlib only).

Branch `p_integral` only, not released. The area holds a light RustRed Ordered step cache
of Vakint's built-in RustRed p library (massless propagator integrals):

    p_integral/manifest.json         schema vakint.external-data.p-integral.v1:
                                     {"schema", "libraries": [] (reserved), "ordered_cache":
                                      {"path": "ordered-cache", "metadata": "ordered-cache.json"},
                                      "files": {<path below p_integral/>: {"sha256", "bytes"}}}
    p_integral/ordered-cache.json    schema vakint.external-data.p-ordered-cache.v1
    p_integral/ordered-cache/<dir>/  ordered-step-cache.txt, shards/*.rrstep, [ordered-tail.rrtail]

declared by the root-manifest key `"p_integral": {"manifest": "p_integral/manifest.json",
"manifest_sha256": ...}`. `<dir>` is Vakint's textual cache directory of the library program,
`p-library-<a>-<b>_<versions>`. The cache is bound by versions only: Vakint uses it iff its
directory name, library identity, RustRed stamp and tail versions are the running build's and
every file matches its sha256; otherwise Vakint prints one line and reduces without it.
`tools/data.py` ignores the area and the key.

Commands:
  stage --export DIR [--replace]   copy DIR/p_integral/{ordered-cache/,ordered-cache.json}
                                   (Vakint's export_ordered_caches, `p_cache_maintenance prepare`)
                                   into the area, write its manifest and set the root key (only
                                   that key of manifest.json changes); refuses an existing area
                                   unless --replace
  validate                         check the area (inventory, sha256/bytes, schema strings, RustRed
                                   manifests and file headers, metadata sums, at most
                                   16,000,000 bytes) and print its bytes; no area and no key is valid
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from data import ROOT, checked_path, digest, file_record, read_json, write_json  # noqa: E402
from ordered_cache import (  # noqa: E402
    FILE_BYTES_LIMIT,
    HEX64,
    RUSTRED_CACHE_SCHEMA,
    RUSTRED_MANIFEST,
    STAGES,
    TAIL_FILE,
    TAIL_SCHEMA,
    check_shard,
    tail_header,
)

ROOT_KEY = "p_integral"
AREA = "p_integral"
AREA_SCHEMA = "vakint.external-data.p-integral.v1"
METADATA_SCHEMA = "vakint.external-data.p-ordered-cache.v1"
SECTION = {"path": "ordered-cache", "metadata": "ordered-cache.json"}
KEY = {"manifest": f"{AREA}/manifest.json"}
BYTES_LIMIT = 16_000_000
ADAPTER = "propagator-library"
TAIL_ADAPTER = "PropagatorLibrary"
DIRECTORY = re.compile(r"p-library-(?P<a>[1-9])-(?P<b>[1-9])_[A-Za-z0-9._-]+")
DIRECTORY_BYTES_LIMIT = 200
DESCRIPTION_KEYS = ("schema", "semantics", "adapter", "family", "variables", "unresolved")
PROGRAM_KEYS = {
    "label", "scope", "directory", "identity", "p_versions", "stamp", "adapter", "records",
    "shards", "bytes", "tail_bytes", "complete", "trim",
}
TRIM_KEYS = {"from_records", "from_shards", "from_bytes", "from_tail_bytes", "method", "selection",
             "full_cache"}


def unescape(text):
    """RustRed's escaping of manifest fields (`%25`, `%20`, `%0A`, `%0D`, `%09`)."""
    for code, character in (("%20", " "), ("%0A", "\n"), ("%0D", "\r"), ("%09", "\t"), ("%25", "%")):
        text = text.replace(code, character)
    return text


def parse_manifest(text):
    """(description {key: value}, stamp, shard rows) of a p program's `ordered-step-cache.txt`."""
    lines = text.split("\n")
    if lines[-1] != "" or len(lines) < len(DESCRIPTION_KEYS) + 3 or lines[-2] != "end":
        raise ValueError("truncated RustRed cache manifest")
    lines = lines[:-2]
    description = {}
    for key, line in zip(DESCRIPTION_KEYS, lines, strict=False):
        if not line.startswith(key + " "):
            raise ValueError(f"RustRed cache manifest line {key!r} missing")
        description[key] = line[len(key) + 1:]
    stamp = lines[len(DESCRIPTION_KEYS)]
    if not stamp.startswith("stamp ") or not HEX64.fullmatch(stamp[6:]):
        raise ValueError("invalid RustRed cache stamp")
    shards = []
    for line in lines[len(DESCRIPTION_KEYS) + 1:]:
        fields = line.split(" ")
        if (
            len(fields) != 8
            or fields[0] != "shard"
            or fields[1] not in STAGES
            or not re.fullmatch(r"[0-9]+", fields[2])
            or not re.fullmatch(r"[0-9a-f]{16}", fields[3])
            or not re.fullmatch(r"shards/[A-Za-z0-9_-][A-Za-z0-9._-]*", fields[4])
            or not re.fullmatch(r"[0-9]+", fields[5])
            or not re.fullmatch(r"[0-9]+", fields[6])
            or not HEX64.fullmatch(fields[7])
        ):
            raise ValueError(f"invalid RustRed shard line {line!r}")
        shards.append({"stage": fields[1], "support": int(fields[2]), "class": int(fields[3], 16),
                       "file": fields[4], "records": int(fields[5]), "bytes": int(fields[6]),
                       "payload_blake3": fields[7]})
    if len({row["file"] for row in shards}) != len(shards):
        raise ValueError("RustRed cache manifest repeats a shard file")
    return description, stamp[6:], shards


def check_program(area, program, versions):
    """Check one program entry of `ordered-cache.json` against its files; returns its file list."""
    if set(program) != PROGRAM_KEYS:
        raise ValueError(f"p cache program keys differ: {sorted(set(program) ^ PROGRAM_KEYS)}")
    directory = program["directory"]
    name = directory.removeprefix(SECTION["path"] + "/")
    match = DIRECTORY.fullmatch(name)
    if (
        not directory.startswith(SECTION["path"] + "/")
        or not match
        or len(name.encode()) > DIRECTORY_BYTES_LIMIT
    ):
        raise ValueError(f"p cache directory {directory!r} is not ordered-cache/p-library-<a>-<b>_...")
    scope = [int(match["a"]), int(match["b"])]
    if program["scope"] != scope or program["label"] != f"p-library-{scope[0]}-{scope[1]}":
        raise ValueError(f"{name}: label {program['label']!r} / scope {program['scope']} differ from the name")
    if not program["identity"].startswith(f"p-library:scope={scope[0]}-{scope[1]}:"):
        raise ValueError(f"{name}: identity {program['identity']!r} is not of scope {scope}")
    base = checked_path(area, directory)
    manifest = base / RUSTRED_MANIFEST
    if manifest.is_symlink() or not manifest.is_file():
        raise ValueError(f"{name}: no {RUSTRED_MANIFEST}")
    description, stamp, shards = parse_manifest(manifest.read_text())
    expected = {
        "schema": RUSTRED_CACHE_SCHEMA,
        "semantics": versions.get("ordered_step_semantics"),
        "adapter": ADAPTER,
        "family": program["identity"],
        "variables": "1 d",
        "unresolved": "reject",
    }
    for key, value in expected.items():
        actual = unescape(description[key]) if key == "family" else description[key]
        if actual != value:
            raise ValueError(f"{name}: RustRed manifest {key} {actual!r}, expected {value!r}")
    if stamp != program["stamp"] or program["adapter"] != ADAPTER:
        raise ValueError(f"{name}: stamp or adapter differs from ordered-cache.json")
    for row in shards:
        check_shard(checked_path(base, row["file"]), stamp, row)
    files = [RUSTRED_MANIFEST] + [row["file"] for row in shards]
    tail_bytes = 0
    if (base / TAIL_FILE).exists() or (base / TAIL_FILE).is_symlink():
        tail = tail_header(base / TAIL_FILE)
        if (
            tail["schema"] != TAIL_SCHEMA
            or tail["semantics"] != versions.get("ordered_tail_semantics")
            or tail["adapter"] != TAIL_ADAPTER
        ):
            raise ValueError(f"{name}: tail table {tail} differs from the producer's versions")
        files.append(TAIL_FILE)
        tail_bytes = tail["bytes"]
    sums = {
        "records": sum(row["records"] for row in shards),
        "shards": len(shards),
        "bytes": sum(row["bytes"] for row in shards),
        "tail_bytes": tail_bytes,
    }
    if any(program[key] != value for key, value in sums.items()):
        raise ValueError(f"{name}: ordered-cache.json counts differ from the files ({sums})")
    if program["complete"] is not (program["trim"] is None):
        raise ValueError(f"{name}: complete {program['complete']} with trim {program['trim']}")
    if program["trim"] is not None and set(program["trim"]) != TRIM_KEYS:
        raise ValueError(f"{name}: trim keys differ from {sorted(TRIM_KEYS)}")
    return [f"{directory}/{file}" for file in files]


def validate(root=ROOT):
    """Validate the area of `root`; returns its bytes (0 without an area)."""
    root = Path(root)
    manifest = read_json(root / "manifest.json")
    area = root / AREA
    if ROOT_KEY not in manifest:
        if area.exists() or area.is_symlink():
            raise ValueError(f"{AREA}/ exists but manifest.json has no key {ROOT_KEY!r}")
        return 0
    key = manifest[ROOT_KEY]
    if not isinstance(key, dict) or set(key) != {"manifest", "manifest_sha256"} or key["manifest"] != KEY["manifest"]:
        raise ValueError(f"manifest.json key {ROOT_KEY!r} is {key!r}")
    if area.is_symlink() or not area.is_dir():
        raise ValueError(f"manifest.json declares {AREA}/, which is missing")
    entries = list(area.rglob("*"))
    if any(path.is_symlink() for path in entries):
        raise ValueError(f"{AREA}/ contains a symlink")
    area_manifest = area / "manifest.json"
    if digest(area_manifest) != key["manifest_sha256"]:
        raise ValueError(f"{AREA}/manifest.json does not match the root key's sha256")
    declared = read_json(area_manifest)
    if declared.get("schema") != AREA_SCHEMA:
        raise ValueError(f"{AREA}/manifest.json schema {declared.get('schema')!r}, expected {AREA_SCHEMA!r}")
    if set(declared) != {"schema", "libraries", "ordered_cache", "files"} or declared["libraries"] != []:
        raise ValueError(f"{AREA}/manifest.json keys differ (libraries are reserved and empty)")
    if declared["ordered_cache"] != SECTION:
        raise ValueError(f"{AREA}/manifest.json ordered_cache is {declared['ordered_cache']!r}")
    files = declared["files"]
    actual = {path.relative_to(area).as_posix() for path in entries if path.is_file()} - {"manifest.json"}
    if actual != set(files):
        raise ValueError(f"{AREA}/ file inventory differs (extra {sorted(actual - set(files))[:3]}, "
                         f"missing {sorted(set(files) - actual)[:3]})")
    for name, expected in files.items():
        if file_record(checked_path(area, name)) != expected:
            raise ValueError(f"{AREA}/{name}: sha256 or size differs from {AREA}/manifest.json")
        if expected["bytes"] > FILE_BYTES_LIMIT:
            raise ValueError(f"{AREA}/{name} exceeds {FILE_BYTES_LIMIT} bytes")
    metadata = read_json(area / SECTION["metadata"])
    if metadata.get("schema") != METADATA_SCHEMA:
        raise ValueError(f"{SECTION['metadata']} schema {metadata.get('schema')!r}, expected {METADATA_SCHEMA!r}")
    versions = metadata.get("producer", {}).get("rustred", {})
    covered = {SECTION["metadata"]}
    labels = [program.get("label") for program in metadata["programs"]]
    if not labels or len(set(labels)) != len(labels):
        raise ValueError(f"{SECTION['metadata']} programs {labels} are empty or repeated")
    for program in metadata["programs"]:
        covered.update(check_program(area, program, versions))
    if covered != set(files):
        raise ValueError(f"{AREA}/ holds files outside its programs: {sorted(set(files) - covered)[:3]}")
    total = sum(path.stat().st_size for path in entries if path.is_file())
    if total > BYTES_LIMIT:
        raise ValueError(f"{AREA}/ holds {total} bytes, above {BYTES_LIMIT}")
    return total


def stage(export, root=ROOT, *, replace=False):
    """Stage an export (`EXPORT/p_integral/...`) into `root`; returns the area bytes."""
    root, source = Path(root), Path(export) / AREA
    area = root / AREA
    if not (source / SECTION["metadata"]).is_file() or not (source / SECTION["path"]).is_dir():
        raise ValueError(f"{source} holds no {SECTION['metadata']} and {SECTION['path']}/")
    if area.exists() or area.is_symlink():
        if not replace:
            raise ValueError(f"{area} exists; pass --replace to regenerate it")
        shutil.rmtree(area)
    area.mkdir()
    shutil.copytree(source / SECTION["path"], area / SECTION["path"])
    shutil.copy2(source / SECTION["metadata"], area / SECTION["metadata"])
    files = {
        path.relative_to(area).as_posix(): file_record(path)
        for path in sorted(area.rglob("*"))
        if path.is_file()
    }
    write_json(area / "manifest.json", {
        "schema": AREA_SCHEMA,
        "libraries": [],
        "ordered_cache": SECTION,
        "files": files,
    })
    manifest = read_json(root / "manifest.json")
    manifest[ROOT_KEY] = {**KEY, "manifest_sha256": digest(area / "manifest.json")}
    write_json(root / "manifest.json", manifest)
    return validate(root)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    staging = commands.add_parser("stage")
    staging.add_argument("--export", required=True, type=Path)
    staging.add_argument("--replace", action="store_true")
    commands.add_parser("validate")
    arguments = parser.parse_args()
    if arguments.command == "stage":
        total = stage(arguments.export, replace=arguments.replace)
    else:
        total = validate()
    print(f"{AREA}/: {total} bytes (limit {BYTES_LIMIT})")


if __name__ == "__main__":
    main()
