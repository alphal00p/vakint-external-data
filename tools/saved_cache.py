"""Source admission for one native five-loop cache file, without a CAS dependency.

SHA256 and gzip framing are checked here. RustRed additionally authenticates
BLAKE3, the native codec, coefficient contexts, terminals and guards; publishing
still requires that native replay gate.
"""

import hashlib
import math
import struct
import zlib
from decimal import Decimal, InvalidOperation

import data

FORMAT = "rustred.saved-application-cache-file.v1"
TARGET_COMPRESSED = 50 * 1024 * 1024
MAX_COMPRESSED = 95 * 1024 * 1024
MAX_DECODED = 1024 * 1024 * 1024
MAGIC = b"RR-CACHE-FILE-01"
HEADER_BYTES = 56


def integer(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


def hash256(value):
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value)
    )


def semantic_digest(directory, manifest):
    """Match Vakint's explicit saved_application_digest binary field encoding."""
    digest = hashlib.sha256(b"vakint-saved-application-cache-v1\0")

    def field(value):
        raw = value.encode() if isinstance(value, str) else value
        digest.update(struct.pack("<Q", len(raw)))
        digest.update(raw)

    field(data.checked_path(directory, "ibps/application.json").read_bytes())
    field(manifest["dimension"])
    field(manifest["normalization"])
    families = sorted(family["fingerprint"] for family in manifest["families"])
    digest.update(struct.pack("<Q", len(families)))
    for family in families:
        field(family)
    masters = sorted(
        (master["family_sha256"], tuple(master["powers"]))
        for master in manifest["masters"]
    )
    digest.update(struct.pack("<Q", len(masters)))
    for family, powers in masters:
        field(family)
        digest.update(struct.pack("<Q", len(powers)))
        for power in powers:
            digest.update(struct.pack("<q", power))
    return list(digest.digest())


def check_gzip(path, identity, decoded_sha256):
    if set(identity) != {
        "compressed_bytes",
        "compressed_blake3",
        "decoded_bytes",
        "decoded_blake3",
    } or not hash256(decoded_sha256):
        raise ValueError("invalid saved cache identity")
    for name in ("compressed_blake3", "decoded_blake3"):
        value = identity[name]
        if (
            not isinstance(value, list)
            or len(value) != 32
            or any(not integer(x, 0, 255) for x in value)
        ):
            raise ValueError("invalid saved cache BLAKE3 identity")
    if (
        not integer(identity["compressed_bytes"], 1, MAX_COMPRESSED)
        or path.stat().st_size != identity["compressed_bytes"]
        or not integer(identity["decoded_bytes"], HEADER_BYTES + 1, MAX_DECODED)
    ):
        raise ValueError("saved cache byte allowance or length differs")
    decoder = zlib.decompressobj(31)
    decoded = 0
    checksum = hashlib.sha256()
    header = bytearray()
    try:
        with path.open("rb") as stream:
            while compressed := stream.read(64 * 1024):
                if decoder.eof:
                    raise ValueError(
                        "saved cache has trailing data or extra gzip members"
                    )
                pending = compressed
                while pending:
                    block = decoder.decompress(
                        pending,
                        min(1024 * 1024, identity["decoded_bytes"] - decoded + 1),
                    )
                    decoded += len(block)
                    if decoded > identity["decoded_bytes"]:
                        raise ValueError("saved cache exceeds its decoded length")
                    checksum.update(block)
                    header.extend(block[: max(0, HEADER_BYTES - len(header))])
                    if decoder.unused_data:
                        raise ValueError(
                            "saved cache has trailing data or extra gzip members"
                        )
                    pending = decoder.unconsumed_tail
    except zlib.error as failure:
        raise ValueError("saved cache gzip CRC or framing is invalid") from failure
    if (
        not decoder.eof
        or decoded != identity["decoded_bytes"]
        or checksum.hexdigest() != decoded_sha256
        or len(header) != HEADER_BYTES
        or header[:16] != MAGIC
        or struct.unpack("<Q", header[16:24])[0] != decoded - HEADER_BYTES
    ):
        raise ValueError("saved cache decoded identity or native framing differs")


def validate_native_profile(profile, selected):
    if (
        not isinstance(profile, dict)
        or profile.get("strict") is not True
        or profile.get("unresolved_policy") != "reject"
        or profile.get("entry_coverage") != "advisory"
        or profile.get("required_root_postcondition")
        != "complete-native-declared-terminals"
    ):
        raise ValueError(
            "saved cache native profile lacks the strict completion policy"
        )
    expected = sorted({tuple(root["powers"]) for root in selected})
    roots = profile.get("roots")
    if not isinstance(roots, list) or len(roots) != len(expected):
        raise ValueError(
            "saved cache native profile roots differ from selected workload"
        )
    actual = []
    for root in roots:
        if (
            not isinstance(root, dict)
            or set(root) != {"namespace", "powers", "coverage_admitted"}
            or not integer(root["namespace"], 0, 0)
            or not isinstance(root["powers"], list)
            or len(root["powers"]) != 15
            or any(
                not integer(power, -(1 << 63), (1 << 63) - 1)
                for power in root["powers"]
            )
            or type(root["coverage_admitted"]) is not bool
        ):
            raise ValueError("invalid saved cache native profile root")
        # Recorded coverage is evidence only; false does not weaken completion.
        actual.append(tuple(root["powers"]))
    if actual != expected:
        raise ValueError(
            "saved cache native profile roots differ from selected workload"
        )


def validate_nativepack(directory, manifest, descriptor):
    """Admit optional NativePack transport metadata, preserving the small default.

    Native index parsing, claimed-generation checks and record semantic validation
    remain the consumer's Native APIs. No coefficient state is imported here.
    """
    import nativepack

    nativepack.validate_descriptor(descriptor)
    families = manifest["families"]
    if (manifest["loop_count"] != 5 or descriptor["loop_count"] != 5
            or len(families) != 1 or len(families[0]["denominators"]) != 15):
        raise ValueError("NativePack source requires the recorded five-loop common family")
    expected = {
        "artifact_digest": semantic_digest(directory, manifest),
        "family_fingerprint": families[0]["fingerprint"],
        "physical_arity": 15,
        "layer": "saved-application-route-apply-v1",
    }
    if descriptor["binding"] != expected:
        raise ValueError("NativePack semantic binding differs from the live application/catalogue")


def validate(directory, manifest):
    cache = manifest["cache"]
    if manifest["loop_count"] != 5 or cache.get("format") != FORMAT:
        raise ValueError("unsupported saved cache format or loop count")
    if cache.get("path") != "cache/prepared.rrcache.gz":
        raise ValueError("five-loop cache must be one native compressed file")
    path = data.checked_path(directory, cache["path"])
    if data.file_record(path) != manifest["files"].get(cache["path"]):
        raise ValueError("saved cache differs from the authenticated file inventory")
    families = manifest["families"]
    if len(families) != 1 or len(families[0]["denominators"]) != 15:
        raise ValueError("saved cache requires the recorded fifteen-slot common family")
    expected_binding = {
        "artifact_digest": semantic_digest(directory, manifest),
        "family_fingerprint": families[0]["fingerprint"],
        "physical_arity": 15,
        "layer": "saved-application-route-apply-v1",
    }
    if cache.get("binding") != expected_binding:
        raise ValueError("saved cache campaign or catalogue binding differs")
    metadata = data.read_json(data.checked_path(directory, cache["metadata"]))
    if (
        metadata.get("schema") != "vakint.external-data.saved-cache.v1"
        or metadata.get("strict") is not True
    ):
        raise ValueError("saved cache must record strict native preparation")
    workload_ref = metadata["workload"]
    workload_path = data.checked_path(directory, workload_ref["path"])
    if data.digest(workload_path) != workload_ref["sha256"]:
        raise ValueError("saved cache workload hash differs")
    workload = data.read_json(workload_path)
    if workload.get("schema") != "vakint.five-loop-cache-workload.v1":
        raise ValueError("unknown selected cache workload")
    if any(
        not hash256(workload.get(name))
        for name in ("data_manifest_sha256", "source_census_sha256")
    ):
        raise ValueError("selected cache workload lacks its frozen input hashes")
    selected = workload["training"]
    if not selected or len(workload["held_out"]) < 12:
        raise ValueError("saved cache workload or held-out set is incomplete")
    sets = []
    names = set()
    for name in ("training", "tuning", "held_out"):
        keys = set()
        for root in workload[name]:
            powers = root["powers"]
            if (
                not root.get("id")
                or root["id"] in names
                or not root.get("rationale", "").strip()
                or len(powers) != 15
                or any(not integer(p, -(1 << 63), (1 << 63) - 1) for p in powers)
                or tuple(powers) in keys
            ):
                raise ValueError("invalid or duplicate selected cache root")
            keys.add(tuple(powers))
            names.add(root["id"])
        sets.append(keys)
    if sets[2] & (sets[0] | sets[1]):
        raise ValueError("held-out cache inputs overlap training or tuning")
    report = metadata["preparation_report"]
    validate_native_profile(report.get("native_profile"), selected)
    elapsed = metadata.get("final_build_elapsed_seconds")
    if (
        report.get("status") != "complete"
        or report.get("failure") is not None
        or type(report.get("completed_roots")) is not int
        or type(report.get("total_roots")) is not int
        or report.get("completed_roots") != len(selected)
        or report.get("total_roots") != len(selected)
        or type(elapsed) not in (int, float)
        or not math.isfinite(elapsed)
        or not 0 <= elapsed <= 36000
    ):
        raise ValueError(
            "saved cache is not a complete selected workload within the build budget"
        )
    check_gzip(path, cache["identity"], cache["decoded_sha256"])
    if cache["identity"]["compressed_bytes"] > TARGET_COMPRESSED:
        exception = metadata.get("size_exception", {})
        evidence_ref = exception.get("comparison", {})
        if (
            exception.get("metric")
            not in {"quadratic-median-ibp", "tuning-geomean-ibp"}
            or not integer(
                exception.get("baseline_compressed_bytes"), 1, TARGET_COMPRESSED
            )
            or not hash256(evidence_ref.get("sha256"))
        ):
            raise ValueError(
                "saved cache above 50 MiB lacks the required performance exception"
            )
        evidence = data.checked_path(directory, evidence_ref["path"])
        if data.digest(evidence) != evidence_ref["sha256"]:
            raise ValueError("saved cache size-exception comparison changed")
        try:
            baseline = Decimal(str(exception.get("baseline_seconds")))
            candidate = Decimal(str(exception.get("candidate_seconds")))
        except InvalidOperation as failure:
            raise ValueError(
                "saved cache size comparison times are invalid"
            ) from failure
        if (
            not baseline.is_finite()
            or not candidate.is_finite()
            or baseline <= 0
            or candidate <= 0
            or candidate > baseline * Decimal("0.8")
        ):
            raise ValueError(
                "saved cache size exception needs at least 20 percent improvement"
            )
