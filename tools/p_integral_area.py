#!/usr/bin/env python3
"""The top-level `p_integral/` area: Vakint's shipped p-integral data (Python stdlib only).

Branch `p_integral` only, not released. The area holds a light RustRed Ordered step cache
of Vakint's RustRed p library (massless propagator integrals) and, optionally, RustRed p
libraries themselves:

    p_integral/manifest.json         schema vakint.external-data.p-integral.v1:
                                     {"schema", "libraries": [<library entry>, ...],
                                      ["ordered_cache": {"path": "ordered-cache",
                                                         "metadata": "ordered-cache.json"},]
                                      "files": {<path below p_integral/>: {"sha256", "bytes"}}}
    p_integral/ordered-cache.json    schema vakint.external-data.p-ordered-cache.v1
    p_integral/ordered-cache/<dir>/  ordered-step-cache.txt, shards/*.rrstep, [ordered-tail.rrtail]
    p_integral/p-library-<a>-<b>/    a RustRed p library (`rustred p-package` output), listed in
                                     `libraries` as {"directory": "p-library-<a>-<b>",
                                     "schema": <its P_LIBRARY_SCHEMA>, "scope": [a, b],
                                     "identity": <its PLibrary identity>,
                                     "files": {<path below the directory>: {"sha256", "bytes"}}}

declared by the root-manifest key `"p_integral": {"manifest": "p_integral/manifest.json",
"manifest_sha256": ...}`. `files` lists every area file outside the libraries; a library
lists its own files. `<dir>` is Vakint's textual cache directory of the library program,
`p-library-<a>-<b>_<versions>`. The cache is bound by versions only: Vakint uses it iff its
directory name, library identity, RustRed stamp and tail versions are the running build's and
every file matches its sha256; otherwise Vakint prints one line and reduces without it.
`tools/data.py` ignores the area and the key.

Limits (user ruling 2026-11-08): every file of the area is below 100,000,000 bytes (GitHub's
hard limit); a file above 50,000,000 bytes must be compressed (`.gz`, `.zst`) or split into
`<name>.part-000`, `<name>.part-001`, ... (contiguous, each at most 50,000,000 bytes; the
file is their concatenation in order). The light-cache budget of 16,000,000 bytes applies
to the cache files (`ordered-cache/`) only; libraries have no budget beyond the per-file rule.

Commands:
  stage --export DIR [--replace]   copy DIR/p_integral/{ordered-cache/,ordered-cache.json}
                                   (Vakint's export_ordered_caches, `p_cache_maintenance prepare`)
                                   into the area, write its manifest and set the root key (only
                                   that key of manifest.json changes); refuses an existing cache
                                   unless --replace; listed libraries are kept
  stage-library --package DIR [--replace]
                                   copy a RustRed p library directory (its library.json gives
                                   schema, identity and scope) to p_integral/p-library-<a>-<b>/
                                   and list it; refuses an existing one unless --replace
  validate                         check the area (inventory, sha256/bytes, schema strings, RustRed
                                   manifests and file headers, metadata sums, libraries, the
                                   per-file rule, the light-cache budget) and print its bytes;
                                   a library of a schema this tool does not know is reported and
                                   checked for integrity only; no area and no key is valid
  light-bytes                      print the bytes of the cache files (`ordered-cache/`, 0 without
                                   an area); exit status 1 above 16,000,000
"""

from __future__ import annotations

import argparse
import dataclasses
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from data import ROOT, checked_path, digest, file_record, read_json, write_json  # noqa: E402
from ordered_cache import (  # noqa: E402
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
FILE_BYTES_LIMIT_HARD = 100_000_000  # GitHub refuses files of 100 MB and more
LARGE_FILE_BYTES = 50_000_000  # above: compressed or split
COMPRESSED_SUFFIXES = (".gz", ".zst")
SPLIT_PART = re.compile(r"(?P<name>.+)\.part-(?P<index>[0-9]{3})")
LIGHT_CACHE_BYTES_LIMIT = 16_000_000  # the files below ordered-cache/
LIBRARY_DIRECTORY = re.compile(r"p-library-(?P<a>[1-9])-(?P<b>[1-9])")
LIBRARY_KEYS = {"directory", "schema", "scope", "identity", "files"}
LIBRARY_DESCRIPTION = "library.json"
LIBRARY_SCHEMAS = {"rustred.p-owner-library.v1"}  # P_LIBRARY_SCHEMA values this tool reads
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


def check_file_rule(sizes):
    """The per-file rule over {path below p_integral/: bytes} (user ruling 2026-11-08)."""
    parts = {}
    for name, size in sorted(sizes.items()):
        if size >= FILE_BYTES_LIMIT_HARD:
            raise ValueError(f"{AREA}/{name}: {size} bytes; every file stays below {FILE_BYTES_LIMIT_HARD}")
        if size > LARGE_FILE_BYTES and not name.endswith(COMPRESSED_SUFFIXES):
            raise ValueError(f"{AREA}/{name}: {size} bytes, above {LARGE_FILE_BYTES}; compress it "
                             f"({', '.join(COMPRESSED_SUFFIXES)}) or split it (<name>.part-000, ...)")
        if match := SPLIT_PART.fullmatch(name):
            parts.setdefault(match["name"], []).append(int(match["index"]))
    for name, indices in parts.items():
        if indices != list(range(len(indices))) or name in sizes:
            raise ValueError(f"{AREA}/{name}: split parts {indices} are not .part-000, .part-001, ... "
                             "without gaps, or the whole file is present too")


def check_library(area, entry):
    """Check one `libraries` entry against its directory; returns (its report, a note or None)."""
    if not isinstance(entry, dict) or set(entry) != LIBRARY_KEYS:
        raise ValueError(f"{AREA}/manifest.json library entry keys differ from {sorted(LIBRARY_KEYS)}: {entry!r}")
    directory, schema, identity, files = entry["directory"], entry["schema"], entry["identity"], entry["files"]
    match = LIBRARY_DIRECTORY.fullmatch(directory) if isinstance(directory, str) else None
    if not match or int(match["a"]) > int(match["b"]):
        raise ValueError(f"library directory {directory!r} is not p-library-<a>-<b> (a <= b)")
    scope = [int(match["a"]), int(match["b"])]
    if entry["scope"] != scope:
        raise ValueError(f"{directory}: scope {entry['scope']!r} differs from the name")
    if not isinstance(schema, str) or not schema:
        raise ValueError(f"{directory}: schema {schema!r} is not a P_LIBRARY_SCHEMA string")
    if not isinstance(identity, str) or not identity.startswith(f"p-library:scope={scope[0]}-{scope[1]}:"):
        raise ValueError(f"{directory}: identity {identity!r} is not of scope {scope}")
    base = area / directory
    if base.is_symlink() or not base.is_dir() or not isinstance(files, dict) or not files:
        raise ValueError(f"{AREA}/{directory}/ is missing or lists no files")
    actual = {path.relative_to(base).as_posix() for path in base.rglob("*") if path.is_file()}
    if actual != set(files):
        raise ValueError(f"{AREA}/{directory}/ file inventory differs (extra {sorted(actual - set(files))[:3]}, "
                         f"missing {sorted(set(files) - actual)[:3]})")
    for name, expected in files.items():
        if file_record(checked_path(base, name)) != expected:
            raise ValueError(f"{AREA}/{directory}/{name}: sha256 or size differs from {AREA}/manifest.json")
    report = {"directory": directory, "schema": schema, "scope": scope,
              "bytes": sum(record["bytes"] for record in files.values()), "supported": schema in LIBRARY_SCHEMAS}
    if not report["supported"]:
        return report, (f"library {directory}: schema {schema!r} is not one this tool reads "
                        f"({sorted(LIBRARY_SCHEMAS)}); its files are checked, its contents are not")
    if LIBRARY_DESCRIPTION not in files:
        raise ValueError(f"{AREA}/{directory}/ has no {LIBRARY_DESCRIPTION}")
    description = read_json(base / LIBRARY_DESCRIPTION)
    for key, value in (("schema", schema), ("identity", identity), ("scope", scope)):
        if description.get(key) != value:
            raise ValueError(f"{directory}/{LIBRARY_DESCRIPTION} {key} {description.get(key)!r} differs from "
                             f"its {AREA}/manifest.json entry {value!r}")
    return report, None


@dataclasses.dataclass
class AreaReport:
    """What `validate` found: the area's bytes, its cache bytes, its libraries and notes."""

    bytes: int = 0
    cache_bytes: int = 0
    libraries: list = dataclasses.field(default_factory=list)
    notes: list = dataclasses.field(default_factory=list)

    def lines(self):
        yield (f"{AREA}/: {self.bytes} bytes; {SECTION['path']}/: {self.cache_bytes} bytes "
               f"(light budget {LIGHT_CACHE_BYTES_LIMIT})")
        for library in self.libraries:
            yield (f"{AREA}/{library['directory']}/: scope {library['scope'][0]}-{library['scope'][1]}, "
                   f"{library['schema']}, {library['bytes']} bytes")
        for note in self.notes:
            yield f"note: {note}"


def validate(root=ROOT):
    """Validate the area of `root`; returns its AreaReport (empty without an area)."""
    root = Path(root)
    manifest = read_json(root / "manifest.json")
    area = root / AREA
    if ROOT_KEY not in manifest:
        if area.exists() or area.is_symlink():
            raise ValueError(f"{AREA}/ exists but manifest.json has no key {ROOT_KEY!r}")
        return AreaReport()
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
    if not {"schema", "libraries", "files"} <= set(declared) <= {"schema", "libraries", "ordered_cache", "files"}:
        raise ValueError(f"{AREA}/manifest.json keys {sorted(declared)} differ from schema, libraries, "
                         "[ordered_cache,] files")
    if "ordered_cache" in declared and declared["ordered_cache"] != SECTION:
        raise ValueError(f"{AREA}/manifest.json ordered_cache is {declared['ordered_cache']!r}")
    if not isinstance(declared["libraries"], list):
        raise ValueError(f"{AREA}/manifest.json libraries is not a list")
    report = AreaReport()
    library_files = set()
    for entry in declared["libraries"]:
        library, note = check_library(area, entry)
        if library["directory"] in {other["directory"] for other in report.libraries}:
            raise ValueError(f"{AREA}/manifest.json lists {library['directory']} twice")
        report.libraries.append(library)
        report.notes += [note] if note else []
        library_files.update(f"{library['directory']}/{name}" for name in entry["files"])
    files = declared["files"]
    sizes = {path.relative_to(area).as_posix(): path.stat().st_size for path in entries if path.is_file()}
    actual = set(sizes) - {"manifest.json"} - library_files
    if actual != set(files):
        raise ValueError(f"{AREA}/ file inventory differs (extra {sorted(actual - set(files))[:3]}, "
                         f"missing {sorted(set(files) - actual)[:3]})")
    for name, expected in files.items():
        if file_record(checked_path(area, name)) != expected:
            raise ValueError(f"{AREA}/{name}: sha256 or size differs from {AREA}/manifest.json")
    check_file_rule(sizes)
    covered = set()
    if "ordered_cache" in declared:
        metadata = read_json(area / SECTION["metadata"])
        if metadata.get("schema") != METADATA_SCHEMA:
            raise ValueError(f"{SECTION['metadata']} schema {metadata.get('schema')!r}, "
                             f"expected {METADATA_SCHEMA!r}")
        versions = metadata.get("producer", {}).get("rustred", {})
        covered.add(SECTION["metadata"])
        labels = [program.get("label") for program in metadata["programs"]]
        if not labels or len(set(labels)) != len(labels):
            raise ValueError(f"{SECTION['metadata']} programs {labels} are empty or repeated")
        for program in metadata["programs"]:
            covered.update(check_program(area, program, versions))
    if covered != set(files):
        raise ValueError(f"{AREA}/ holds files outside its programs and libraries: "
                         f"{sorted(set(files) - covered)[:3]}")
    report.bytes = sum(sizes.values())
    report.cache_bytes = cache_bytes(sizes)
    if report.cache_bytes > LIGHT_CACHE_BYTES_LIMIT:
        raise ValueError(f"{AREA}/{SECTION['path']}/ holds {report.cache_bytes} bytes, above the light-cache "
                         f"budget {LIGHT_CACHE_BYTES_LIMIT}")
    return report


def cache_bytes(sizes):
    """The bytes of the cache files among {path below p_integral/: bytes}."""
    return sum(size for name, size in sizes.items() if name.startswith(SECTION["path"] + "/"))


def light_bytes(root=ROOT):
    """The bytes of the files below `root/p_integral/ordered-cache/` (0 without them); no other check."""
    cache = Path(root) / AREA / SECTION["path"]
    if not cache.is_dir():
        return 0
    return sum(path.stat().st_size for path in cache.rglob("*") if path.is_file() and not path.is_symlink())


def write_area(root, libraries):
    """Write the area manifest (every file outside `libraries` listed) and the root key."""
    area = Path(root) / AREA
    library_directories = {entry["directory"] for entry in libraries}
    files = {
        path.relative_to(area).as_posix(): file_record(path)
        for path in sorted(area.rglob("*"))
        if path.is_file() and path.relative_to(area).parts[0] not in library_directories | {"manifest.json"}
    }
    declared = {"schema": AREA_SCHEMA, "libraries": sorted(libraries, key=lambda entry: entry["directory"])}
    if (area / SECTION["metadata"]).exists():
        declared["ordered_cache"] = SECTION
    write_json(area / "manifest.json", {**declared, "files": files})
    manifest = read_json(Path(root) / "manifest.json")
    manifest[ROOT_KEY] = {**KEY, "manifest_sha256": digest(area / "manifest.json")}
    write_json(Path(root) / "manifest.json", manifest)


def listed_libraries(root):
    """The `libraries` entries of an existing area (none without one)."""
    area_manifest = Path(root) / AREA / "manifest.json"
    return read_json(area_manifest)["libraries"] if area_manifest.is_file() else []


def stage(export, root=ROOT, *, replace=False):
    """Stage an export (`EXPORT/p_integral/...`) into `root`, keeping listed libraries; returns the report."""
    root, source = Path(root), Path(export) / AREA
    area = root / AREA
    if not (source / SECTION["metadata"]).is_file() or not (source / SECTION["path"]).is_dir():
        raise ValueError(f"{source} holds no {SECTION['metadata']} and {SECTION['path']}/")
    libraries = listed_libraries(root)
    if (area / SECTION["path"]).exists() or (area / SECTION["metadata"]).exists():
        if not replace:
            raise ValueError(f"{area} holds a cache; pass --replace to regenerate it")
        shutil.rmtree(area / SECTION["path"], ignore_errors=True)
        (area / SECTION["metadata"]).unlink(missing_ok=True)
    area.mkdir(exist_ok=True)
    shutil.copytree(source / SECTION["path"], area / SECTION["path"])
    shutil.copy2(source / SECTION["metadata"], area / SECTION["metadata"])
    write_area(root, libraries)
    return validate(root)


def stage_library(package, root=ROOT, *, replace=False):
    """Copy a RustRed p library directory into the area and list it; returns the report."""
    root, package = Path(root), Path(package)
    description = read_json(package / LIBRARY_DESCRIPTION)
    scope = description.get("scope")
    if not (isinstance(scope, list) and len(scope) == 2 and all(type(n) is int and 1 <= n <= 9 for n in scope)):
        raise ValueError(f"{package / LIBRARY_DESCRIPTION}: scope {scope!r} is not [a, b]")
    directory = f"p-library-{scope[0]}-{scope[1]}"
    sources = sorted(path for path in package.rglob("*") if path.is_file())
    check_file_rule({f"{directory}/{path.relative_to(package).as_posix()}": path.stat().st_size for path in sources})
    area = root / AREA
    libraries = [entry for entry in listed_libraries(root) if entry["directory"] != directory]
    if (area / directory).exists():
        if not replace:
            raise ValueError(f"{area / directory} exists; pass --replace to regenerate it")
        shutil.rmtree(area / directory)
    area.mkdir(exist_ok=True)
    shutil.copytree(package, area / directory)
    files = {path.relative_to(area / directory).as_posix(): file_record(path)
             for path in sorted((area / directory).rglob("*")) if path.is_file()}
    libraries.append({"directory": directory, "schema": description.get("schema"), "scope": scope,
                      "identity": description.get("identity"), "files": files})
    write_area(root, libraries)
    return validate(root)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    staging = commands.add_parser("stage")
    staging.add_argument("--export", required=True, type=Path)
    staging.add_argument("--replace", action="store_true")
    library = commands.add_parser("stage-library")
    library.add_argument("--package", required=True, type=Path)
    library.add_argument("--replace", action="store_true")
    commands.add_parser("validate")
    commands.add_parser("light-bytes")
    arguments = parser.parse_args()
    if arguments.command == "light-bytes":
        total = light_bytes()
        print(f"{AREA}/{SECTION['path']}/: {total} bytes (light budget {LIGHT_CACHE_BYTES_LIMIT})")
        sys.exit(1 if total > LIGHT_CACHE_BYTES_LIMIT else 0)
    if arguments.command == "stage":
        report = stage(arguments.export, replace=arguments.replace)
    elif arguments.command == "stage-library":
        report = stage_library(arguments.package, replace=arguments.replace)
    else:
        report = validate()
    print("\n".join(report.lines()))


if __name__ == "__main__":
    main()
