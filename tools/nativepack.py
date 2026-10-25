"""Metadata and deterministic containers for opaque NativePack files.

This module never parses Native indexes or chunks. SHA256/container validation
does not establish Native binding, generation, record completeness or semantics.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
import re
import shutil
import stat
import tarfile
import tempfile
import unicodedata
import zlib
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA = "vakint.nativepack-transport.v1"
PART_BYTES_LIMIT = 1_800_000_000
TAR_BYTES_TARGET = 1_790_000_000
U64_MAX = (1 << 64) - 1
_HEX = r"[0-9a-f]{64}"
_CHILD = rf"cache/bindings/({_HEX})/cache\.rrindex"
_CHUNK = rf"cache/bindings/({_HEX})/chunks/{_HEX}\.rrchunk\.gz"
_ARCHIVE = r"[A-Za-z0-9][A-Za-z0-9._-]*\.tar\.gz"
_FIELDS = {
    "schema",
    "loop_count",
    "binding",
    "generation",
    "stored_record_references",
    "files",
    "parts",
}


def _integer(value, minimum=0, maximum=U64_MAX):
    return type(value) is int and minimum <= value <= maximum


def _sha(value):
    return isinstance(value, str) and re.fullmatch(_HEX, value) is not None


def _record(value):
    return (
        isinstance(value, dict)
        and set(value) == {"bytes", "sha256"}
        and _integer(value["bytes"], 1)
        and _sha(value["sha256"])
    )


def _kind(name):
    if name == "cache/bundle.rrindex" or re.fullmatch(_CHILD, name):
        return "indexes"
    if re.fullmatch(_CHUNK, name):
        return "chunks"
    raise ValueError(f"unsafe or non-Native file path: {name!r}")


def _url(value):
    if not isinstance(value, str) or any(
        c.isspace() or unicodedata.category(c) == "Cc" for c in value
    ):
        return False
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and not parsed.fragment
            and "#" not in value
            and "\\" not in value
            and (parsed.port is None or 1 <= parsed.port <= 65535)
        )
    except ValueError:
        return False


def validate_descriptor(value):
    """Validate the exact transport schema; return the original dictionary."""
    if (
        not isinstance(value, dict)
        or set(value) != _FIELDS
        or value["schema"] != SCHEMA
    ):
        raise ValueError("invalid NativePack descriptor fields or schema")
    if not _integer(value["loop_count"], 1, 5):
        raise ValueError("invalid NativePack loop_count")
    binding = value["binding"]
    if not isinstance(binding, dict) or set(binding) != {
        "artifact_digest",
        "family_fingerprint",
        "physical_arity",
        "layer",
    }:
        raise ValueError("invalid NativePack binding fields")
    digest = binding["artifact_digest"]
    if (
        not isinstance(digest, list)
        or len(digest) != 32
        or any(not _integer(byte, 0, 255) for byte in digest)
        or not _integer(binding["physical_arity"], 1)
        or any(
            not isinstance(binding[key], str) or not binding[key]
            for key in ("family_fingerprint", "layer")
        )
    ):
        raise ValueError("invalid NativePack binding values")
    for key in ("family_fingerprint", "layer"):
        try:
            binding[key].encode("utf-8")
        except UnicodeError as error:
            raise ValueError("NativePack binding strings must be UTF-8") from error
    if any(
        not _integer(value[key]) for key in ("generation", "stored_record_references")
    ):
        raise ValueError("invalid NativePack generation or stored reference count")
    files = value["files"]
    if not isinstance(files, dict) or not files:
        raise ValueError("NativePack files must be a nonempty inventory")
    children = set()
    namespaces = set()
    for name, row in files.items():
        if not isinstance(name, str):
            raise ValueError("NativePack file names must be strings")  # noqa: TRY004
        _kind(name)
        if not _record(row):
            raise ValueError(f"invalid NativePack file identity: {name}")
        if match := re.fullmatch(_CHILD, name):
            children.add(match[1])
        if match := re.fullmatch(_CHUNK, name):
            namespaces.add(match[1])
    if (
        "cache/bundle.rrindex" not in files
        or len(children) != 1
        or not namespaces <= children
    ):
        raise ValueError(
            "NativePack inventory requires a bundle and exactly one binding namespace"
        )
    parts = value["parts"]
    if not isinstance(parts, list) or not parts:
        raise ValueError("NativePack parts must be a nonempty list")
    names, members = set(), set()
    index_parts = 0
    for part in parts:
        if not isinstance(part, dict) or set(part) not in (
            {"kind", "archive", "archive_bytes", "archive_sha256", "members"},
            {"kind", "archive", "archive_bytes", "archive_sha256", "members", "url"},
        ):
            raise ValueError("invalid NativePack part fields")
        name = part["archive"]
        if (
            not isinstance(name, str)
            or not re.fullmatch(_ARCHIVE, name)
            or name in names
            or len(name.encode("ascii")) > 255
        ):
            raise ValueError("unsafe or duplicate NativePack archive name")
        names.add(name)
        if not _integer(part["archive_bytes"], 1, PART_BYTES_LIMIT) or not _sha(
            part["archive_sha256"]
        ):
            raise ValueError("invalid NativePack archive length or SHA256")
        if "url" in part and not _url(part["url"]):
            raise ValueError(
                "NativePack part URL must be HTTPS without credentials or fragment"
            )
        selected = part["members"]
        if (
            not isinstance(selected, list)
            or not selected
            or any(not isinstance(path, str) for path in selected)
            or selected != sorted(set(selected))
        ):
            raise ValueError("NativePack part members must be unique and sorted")
        if part["kind"] not in ("indexes", "chunks"):
            raise ValueError("invalid NativePack part kind")
        index_parts += part["kind"] == "indexes"
        for path in selected:
            if path not in files or _kind(path) != part["kind"] or path in members:
                raise ValueError(
                    "NativePack member kind, inventory or global uniqueness differs"
                )
            members.add(path)
    if index_parts != 1 or members != set(files):
        raise ValueError(
            "NativePack parts must partition all files with exactly one index part"
        )
    return value


def _path(root, relative):
    """Reject every symlink component, including redirects that stay in root."""
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("NativePack root must be a regular directory")
    if (
        not isinstance(relative, str)
        or not relative
        or "\\" in relative
        or relative.startswith("/")
        or "\0" in relative
        or any(part in ("", ".", "..") for part in relative.split("/"))
    ):
        raise ValueError("unsafe NativePack relative path")
    path = root
    for component in relative.split("/"):
        path = path / component
        if path.is_symlink():
            raise ValueError(f"NativePack path contains symlink: {relative}")
    return path


def _file_record(path, *, expected_bytes=None):
    status = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(status.st_mode):
        raise ValueError(f"NativePack payload must be a regular file: {path}")
    if expected_bytes is not None and status.st_size != expected_bytes:
        raise ValueError("NativePack archive checksum or size differs")
    with path.open("rb") as stream:
        return {
            "bytes": status.st_size,
            "sha256": hashlib.file_digest(stream, "sha256").hexdigest(),
        }


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate NativePack JSON key: {key}")
        result[key] = value
    return result


def _decode_json(raw):
    def reject_constant(value):
        raise ValueError(f"non-finite NativePack JSON constant: {value}")

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_object,
            parse_constant=reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid NativePack JSON") from error


def read_json(path):
    """Read UTF-8 JSON, rejecting duplicate keys and non-finite constants."""
    return _decode_json(Path(path).read_bytes())


def validate_reference(root, row):
    """Authenticate a root-manifest descriptor reference before parsing it."""
    if (
        not isinstance(row, dict)
        or set(row) != {"loop_count", "manifest", "manifest_sha256", "manifest_bytes"}
        or not _integer(row["loop_count"], 1, 5)
        or not _integer(row["manifest_bytes"], 1)
        or not _sha(row["manifest_sha256"])
        or not isinstance(row["manifest"], str)
        or not re.fullmatch(
            rf"{row['loop_count']}L/cache/[A-Za-z0-9][A-Za-z0-9._-]*\.json",
            row["manifest"],
        )
    ):
        raise ValueError("invalid NativePack descriptor reference")
    path = _path(root, row["manifest"])
    status = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(status.st_mode):
        raise ValueError("NativePack descriptor must be a regular file")
    if status.st_size != row["manifest_bytes"]:
        raise ValueError("NativePack descriptor reference checksum or size differs")
    with path.open("rb") as stream:
        raw = stream.read(row["manifest_bytes"] + 1)
    if (
        len(raw) != row["manifest_bytes"]
        or hashlib.sha256(raw).hexdigest() != row["manifest_sha256"]
    ):
        raise ValueError("NativePack descriptor reference checksum or size differs")
    value = _decode_json(raw)
    validate_descriptor(value)
    if value["loop_count"] != row["loop_count"]:
        raise ValueError("NativePack descriptor and reference loop_count differ")
    return value


def assets(manifest, root):
    """Flatten authenticated snapshot parts, deduplicating identical asset rows."""
    if not isinstance(manifest, dict):
        raise ValueError("NativePack root manifest must be an object")  # noqa: TRY004
    references = manifest.get("runtime_cache_snapshots", [])
    if not isinstance(references, list):
        raise ValueError("runtime_cache_snapshots must be a list")  # noqa: TRY004
    result, paths = {}, set()
    for row in references:
        descriptor = validate_reference(root, row)
        if row["manifest"] in paths:
            raise ValueError("duplicate NativePack descriptor reference")
        paths.add(row["manifest"])
        for part in descriptor["parts"]:
            if part["archive"] in result and result[part["archive"]] != part:
                raise ValueError("conflicting NativePack asset identities")
            result[part["archive"]] = part
    return list(result.values())


def _header(name, size):
    info = tarfile.TarInfo(name)
    info.size, info.mode = size, 0o644
    info.uid = info.gid = info.mtime = 0
    info.uname = info.gname = ""
    return info


def _tar_bytes(members, files):
    blocks = (
        sum(512 + ((files[name]["bytes"] + 511) // 512) * 512 for name in members)
        + 1024
    )
    return (
        (blocks + tarfile.RECORDSIZE - 1) // tarfile.RECORDSIZE
    ) * tarfile.RECORDSIZE


def _gzip_bound(size):
    # Conservative zlib compressBound plus extra gzip/header margin.
    return size + (size >> 12) + (size >> 14) + (size >> 25) + 64


def _inflated(stream, expected):
    compressed = stream.read(10)
    if compressed != b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x02\xff":
        raise ValueError("NativePack gzip metadata differs from deterministic format")
    decoder = zlib.decompressobj(31)
    decoded = 0
    try:
        while compressed:
            pending = compressed
            while pending:
                block = decoder.decompress(
                    pending, min(64 * 1024, expected - decoded + 1)
                )
                decoded += len(block)
                if decoded > expected:
                    raise ValueError("NativePack archive exceeds planned tar size")
                if block:
                    yield block
                if decoder.eof:
                    if decoder.unused_data or stream.read(1):
                        raise ValueError(
                            "NativePack archive has trailing bytes or extra gzip members"
                        )
                    if decoded != expected:
                        raise ValueError("NativePack tar length differs")
                    return
                pending = decoder.unconsumed_tail
            compressed = stream.read(64 * 1024)
    except zlib.error as error:
        raise ValueError("NativePack gzip CRC or framing differs") from error
    raise ValueError("truncated NativePack gzip stream")


class _Reader:
    def __init__(self, blocks):
        self.blocks, self.pending = iter(blocks), b""

    def read(self, size):
        while len(self.pending) < size:
            block = next(self.blocks, b"")
            if not block:
                break
            self.pending += block
        result, self.pending = self.pending[:size], self.pending[size:]
        return result


class _AuthenticatedReader:
    def __init__(self, stream, row):
        self.stream, self.row = stream, row
        self.digest, self.consumed = hashlib.sha256(), 0

    def read(self, size):
        value = self.stream.read(size)
        self.consumed += len(value)
        self.digest.update(value)
        if self.consumed > self.row["archive_bytes"]:
            raise ValueError("NativePack archive exceeds declared size")
        return value

    def check(self):
        if (
            self.consumed != self.row["archive_bytes"]
            or self.digest.hexdigest() != self.row["archive_sha256"]
        ):
            raise ValueError("NativePack archive checksum or size differs")


def _verify_part(descriptor, part, directory):
    files = descriptor["files"]
    expected = _tar_bytes(part["members"], files)
    if _gzip_bound(expected) > PART_BYTES_LIMIT:
        raise ValueError("NativePack planned tar exceeds a single part allowance")
    path = _path(directory, part["archive"])
    if _file_record(path, expected_bytes=part["archive_bytes"]) != {
        "bytes": part["archive_bytes"],
        "sha256": part["archive_sha256"],
    }:
        raise ValueError("NativePack archive checksum or size differs")
    with path.open("rb") as compressed:
        authenticated = _AuthenticatedReader(compressed, part)
        stream = _Reader(_inflated(authenticated, expected))
        consumed = 0
        for name in part["members"]:
            row = files[name]
            if stream.read(512) != _header(name, row["bytes"]).tobuf(
                format=tarfile.USTAR_FORMAT
            ):
                raise ValueError(
                    "NativePack USTAR header, member order or metadata differs"
                )
            remaining, digest = row["bytes"], hashlib.sha256()
            while remaining:
                block = stream.read(min(remaining, 64 * 1024))
                if not block:
                    raise ValueError("truncated NativePack tar member")
                remaining -= len(block)
                digest.update(block)
            if digest.hexdigest() != row["sha256"]:
                raise ValueError("NativePack member checksum differs")
            padding = (-row["bytes"]) % 512
            if stream.read(padding) != bytes(padding):
                raise ValueError("NativePack member padding differs")
            consumed += 512 + row["bytes"] + padding
        if stream.read(expected - consumed) != bytes(
            expected - consumed
        ) or stream.read(1):
            raise ValueError("NativePack tar terminators or trailing data differ")
        authenticated.check()


def verify_archives(descriptor, directory):
    """Stream all declared containers; URLs are ignored for local verification."""
    validate_descriptor(descriptor)
    for part in descriptor["parts"]:
        _verify_part(descriptor, part, directory)


class _BoundedWriter:
    def __init__(self, stream, limit):
        self.stream, self.limit, self.written = stream, limit, 0

    def write(self, value):
        self.written += len(value)
        if self.written > self.limit:
            raise ValueError("NativePack compressed part exceeds byte allowance")
        return self.stream.write(value)

    def flush(self):
        return self.stream.flush()


def _identifier(value, rows):
    if value is None:
        return hashlib.sha256(
            json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", value
    ):
        raise ValueError("invalid NativePack stable part identifier")
    return value


def _inventory(source):
    files = {}
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source).as_posix()
        if path.is_symlink():
            raise ValueError("NativePack source contains symlink")
        if re.fullmatch(rf"(?:bindings/{_HEX}/)?writer\.lock", relative):
            status = path.stat(follow_symlinks=False)
            if not stat.S_ISREG(status.st_mode) or status.st_size != 0:
                raise ValueError("NativePack writer.lock must be an empty regular file")
            # Native retains these files after closing a writer. Their omission
            # is a metadata filter; the caller must still select a sealed source.
            continue
        if path.is_dir():
            if not re.fullmatch(rf"bindings(?:/{_HEX}(?:/chunks)?)?", relative):
                raise ValueError("NativePack source contains non-Native directory")
            continue
        name = f"cache/{relative}"
        _kind(name)
        files[name] = _file_record(path)
    return files


def pack_parts(
    source,
    output,
    *,
    binding,
    generation,
    stored_record_references,
    loop_count=5,
    chunk_id=None,
    snapshot_id=None,
    part_bytes_limit=PART_BYTES_LIMIT,
    tar_bytes_target=TAR_BYTES_TARGET,
    base_descriptor=None,
    base_archives=None,
):
    """Package a sealed bundle root (bundle.rrindex and bindings/) without edits.

    The output must be new or empty and outside source. Files remain opaque.
    Exact empty regular Native writer.lock files are ignored and left untouched;
    their presence or absence does not establish that a snapshot is sealed.
    Optional base chunk containers are verified and copied byte for byte; their
    old index container is never selected. All outputs publish only after checks.
    """
    source, output = Path(source), Path(output)
    if source.is_symlink() or not source.is_dir() or output.is_symlink():
        raise ValueError("NativePack source/output must be regular directories")
    source, output = source.absolute(), output.absolute()
    if output.resolve().is_relative_to(
        source.resolve()
    ) or source.resolve().is_relative_to(output.resolve()):
        raise ValueError("NativePack output must be outside the source bundle")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("NativePack output directory must be empty")
    if not _integer(part_bytes_limit, 1, PART_BYTES_LIMIT) or not _integer(
        tar_bytes_target, 1
    ):
        raise ValueError("invalid NativePack partition byte allowance")
    files = _inventory(source)
    result = {
        "schema": SCHEMA,
        "loop_count": loop_count,
        "binding": copy.deepcopy(binding),
        "generation": generation,
        "stored_record_references": stored_record_references,
        "files": files,
        "parts": [],
    }
    indexes = sorted(name for name in files if _kind(name) == "indexes")
    chunks = sorted(name for name in files if _kind(name) == "chunks")
    # Validate all metadata and inventory before creating any archive.
    stub = {
        "kind": "indexes",
        "archive": "validate.tar.gz",
        "archive_bytes": 1,
        "archive_sha256": "0" * 64,
        "members": indexes,
    }
    result["parts"] = [stub]
    if chunks:
        result["parts"].append(
            {**stub, "kind": "chunks", "archive": "chunks.tar.gz", "members": chunks}
        )
    validate_descriptor(result)
    result["parts"] = []
    covered = set()
    if (base_descriptor is None) != (base_archives is None):
        raise ValueError(
            "NativePack base descriptor and archive directory are both required"
        )
    if base_descriptor is not None:
        validate_descriptor(base_descriptor)
        if (
            base_descriptor["binding"] != binding
            or base_descriptor["loop_count"] != loop_count
        ):
            raise ValueError("NativePack reusable base binding or loop_count differs")
        for part in base_descriptor["parts"]:
            if part["kind"] != "chunks":
                continue
            if part["archive_bytes"] > part_bytes_limit or any(
                files.get(name) != base_descriptor["files"][name]
                for name in part["members"]
            ):
                raise ValueError(
                    "NativePack reusable chunks differ from source inventory or allowance"
                )
            _verify_part(base_descriptor, part, base_archives)
            result["parts"].append(copy.deepcopy(part))
            covered.update(part["members"])
    fresh = [name for name in chunks if name not in covered]

    def fits(members):
        size = _tar_bytes(members, files)
        return size <= tar_bytes_target and _gzip_bound(size) <= part_bytes_limit

    if not fits(indexes):
        raise ValueError("NativePack indexes cannot fit one indivisible index part")
    groups, current = [], []
    for name in fresh:
        if not fits([name]):
            raise ValueError(
                f"indivisible NativePack file exceeds part allowance: {name}"
            )
        if current and not fits(current + [name]):
            groups.append(current)
            current = []
        current.append(name)
    if current:
        groups.append(current)
    chunk_id = _identifier(
        chunk_id, [{name: files[name] for name in group} for group in groups]
    )
    snapshot_id = _identifier(
        snapshot_id,
        {
            "files": files,
            "binding": binding,
            "generation": generation,
            "stored_record_references": stored_record_references,
            "loop_count": loop_count,
        },
    )
    plans = [
        (
            "chunks",
            f"cache-{loop_count}L-chunks-{chunk_id}.part{index:04d}.tar.gz",
            members,
        )
        for index, members in enumerate(groups, 1)
    ]
    plans.append(
        (
            "indexes",
            f"cache-{loop_count}L-snapshot-{snapshot_id}.indexes.tar.gz",
            indexes,
        )
    )
    if len(
        {part["archive"] for part in result["parts"]} | {name for _, name, _ in plans}
    ) != len(result["parts"]) + len(plans):
        raise ValueError("NativePack new part names conflict with reusable assets")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".nativepack-", dir=output.parent
    ) as temporary:
        staging = Path(temporary)
        for part in result["parts"]:
            shutil.copyfile(
                _path(base_archives, part["archive"]), staging / part["archive"]
            )
        for kind, name, members in plans:
            target = staging / name
            with (
                target.open("xb") as raw,
                gzip.GzipFile(
                    filename="",
                    mode="wb",
                    fileobj=_BoundedWriter(raw, part_bytes_limit),
                    mtime=0,
                    compresslevel=9,
                ) as compressed,
                tarfile.open(
                    fileobj=compressed, mode="w|", format=tarfile.USTAR_FORMAT
                ) as archive,
            ):
                for member in members:
                    with _path(source, member.removeprefix("cache/")).open(
                        "rb"
                    ) as payload:
                        archive.addfile(
                            _header(member, files[member]["bytes"]), payload
                        )
            identity = _file_record(target)
            result["parts"].append(
                {
                    "kind": kind,
                    "archive": name,
                    "archive_bytes": identity["bytes"],
                    "archive_sha256": identity["sha256"],
                    "members": members,
                }
            )
        validate_descriptor(result)
        verify_archives(result, staging)
        # Detect changed, added and removed source files before atomic publication.
        if _inventory(source) != files:
            raise ValueError("NativePack source changed while packing")
        staging.replace(output)
    return result
