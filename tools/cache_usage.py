"""Portable source admission for usage-selected strict LIGHT caches.

This checks authenticated public eligibility, summary arithmetic and Native
validation bindings. It neither decodes Native records nor replays large traces.
"""

import argparse
import base64
import collections
import gzip
import hashlib
import json
import os
import re
import shutil
import tempfile
import zlib
from pathlib import Path, PurePosixPath

import data
from saved_cache import hash256, integer

U64_MAX = (1 << 64) - 1
GIT_FILE_BYTES_LIMIT = 100 * 1024 * 1024
COHORT_FIELDS = {
    "main_revision": "VAKINT_CACHE_BUILD_GIT_REVISION",
    "native_revision": "VAKINT_CACHE_BUILD_RUSTRED_REVISION",
    "kernel_revision": "VAKINT_CACHE_BUILD_SYMBOLICA_REVISION",
    "main_source_snapshot_sha256": "VAKINT_CACHE_BUILD_MAIN_SOURCE_SNAPSHOT_SHA256",
    "native_source_snapshot_sha256": "VAKINT_CACHE_BUILD_NATIVE_SOURCE_SNAPSHOT_SHA256",
}
PHYSICAL_COLLECTOR_HELPERS = {
    f"crates/vakint/examples/build_cache/{name}.rs"
    for name in (
        "cache_identity",
        "cache_hit_diagnostic",
        "cache_hit_capture",
        "cache_file_args",
        "resource_guard_admission",
    )
}
PROFILE_V2_SCHEMA = "vakint.cache-record-usage-profile.v2"
# Frozen source-only contract; never substitute the v1 schema stamp for v2.
PROFILE_V2_SCHEMA_SHA256 = (
    "3d8bc402451ebeab16a67b5119eaaaa19b0410d905dcffbf75c5bf95bcf945e4"
)
COMMON_COHORT_FIELDS = (
    *COHORT_FIELDS,
    "profile",
    "rustc",
    "collector_artifacts",
    "main_source_snapshot",
    "native_source_snapshot",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(value, expected, message):
    require(isinstance(value, dict) and set(value) == set(expected), message)


def same(left, right):
    """JSON identity must distinguish booleans, integers and decimal values."""
    return json.dumps(
        left, sort_keys=True, separators=(",", ":"), allow_nan=False
    ) == json.dumps(right, sort_keys=True, separators=(",", ":"), allow_nan=False)


def semantic_binding(value):
    fields(
        value,
        ("artifact_digest", "family_fingerprint", "physical_arity", "layer"),
        "invalid usage semantic binding",
    )
    digest = value["artifact_digest"]
    require(
        isinstance(digest, list)
        and len(digest) == 32
        and all(integer(byte, 0, 255) for byte in digest)
        and type(value["physical_arity"]) is int
        and value["physical_arity"] == 15
        and isinstance(value["family_fingerprint"], str)
        and value["family_fingerprint"]
        and value["layer"] == "saved-application-route-apply-v1",
        "invalid usage Native binding values",
    )


def decode_json(raw):
    def unique(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate source proof JSON key")
            result[key] = value
        return result

    def invalid_constant(_value):
        raise ValueError("nonfinite source proof JSON value")

    return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid_constant)


def source_file(root, reference):
    fields(reference, ("path", "sha256"), "invalid source provenance reference")
    relative = reference["path"]
    require(
        isinstance(relative, str)
        and relative.startswith("provenance/")
        and hash256(reference["sha256"]),
        "source proof needs a root-relative provenance path and SHA256",
    )
    path = data.checked_path(root, relative)
    current = root
    for part in PurePosixPath(relative).parts:
        current /= part
        require(not current.is_symlink(), "source proof path contains a symlink")
    require(
        path.is_file() and path.stat().st_size < GIT_FILE_BYTES_LIMIT,
        "source proof must be a regular repository file smaller than 100 MiB",
    )
    require(data.digest(path) == reference["sha256"], "source proof SHA256 differs")
    return path


def source_json(root, reference):
    path = source_file(root, reference)
    if path.name.endswith(".json.gz"):
        try:
            decoder = zlib.decompressobj(31)
            plain = bytearray()
            with path.open("rb") as stream:
                while block := stream.read(64 * 1024):
                    plain.extend(
                        decoder.decompress(block, GIT_FILE_BYTES_LIMIT - len(plain))
                    )
                    require(
                        len(plain) < GIT_FILE_BYTES_LIMIT,
                        "decoded source proof must be smaller than 100 MiB",
                    )
                    require(
                        not decoder.unused_data,
                        "source proof has trailing data or extra gzip members",
                    )
            require(decoder.eof, "source proof gzip is truncated")
            return decode_json(plain)
        except (OSError, EOFError, zlib.error) as error:
            raise ValueError("source proof gzip framing or CRC is invalid") from error
    require(path.name.endswith(".json"), "source proof must be JSON or JSON gzip")
    return decode_json(path.read_bytes())


def work(value, arity):
    require(isinstance(value, dict), "invalid Native work identity")
    kind = value.get("kind")
    fields(
        value,
        ("kind", "powers", "owner_sector") if kind == "apply" else ("kind", "powers"),
        "unknown or malformed Native work identity",
    )
    powers = value["powers"]
    require(
        kind in ("route", "apply")
        and isinstance(powers, list)
        and len(powers) == arity
        and all(integer(power, -(1 << 63), (1 << 63) - 1) for power in powers),
        "Native work powers or stage differ",
    )
    if kind == "apply":
        owner = value["owner_sector"]
        require(
            isinstance(owner, list)
            and len(owner) == arity
            and all(type(active) is bool for active in owner)
            and owner == [power > 0 for power in powers],
            "Native Apply owner differs from positive power support",
        )
        return kind, tuple(powers), tuple(owner)
    return kind, tuple(powers)


def checked_sum(values):
    total = 0
    for value in values:
        require(integer(value, 0, U64_MAX), "invalid usage counter")
        total += value
        require(total <= U64_MAX, "usage counter overflow")
    return total


def dispatch_frequencies(case, arity):
    dispatches = case["dispatches"]
    require(
        isinstance(dispatches, list)
        and integer(case["input_dispatch_count"], 0, U64_MAX)
        and len(dispatches) == case["input_dispatch_count"],
        "usage profile omitted an input dispatch",
    )
    result = collections.Counter()
    for ordinal, dispatch in enumerate(dispatches):
        fields(
            dispatch,
            (
                "ordinal",
                "requested_roots",
                "completed_roots",
                "collected_roots",
                "persistent",
                "records",
            ),
            "invalid usage dispatch fields",
        )
        require(
            type(dispatch["ordinal"]) is int and dispatch["ordinal"] == ordinal,
            "nonconsecutive usage dispatch",
        )
        roots = dispatch["collected_roots"]
        require(isinstance(roots, list), "invalid collected roots")
        roots = [work(root, arity) for root in roots]
        require(
            all(root[0] == "route" for root in roots)
            and len(set(roots)) == len(roots)
            and integer(dispatch["requested_roots"], 0, U64_MAX)
            and integer(dispatch["completed_roots"], 0, U64_MAX)
            and len(roots)
            == dispatch["requested_roots"]
            == dispatch["completed_roots"],
            "usage dispatch roots are incomplete or duplicated",
        )
        persistent = dispatch["persistent"]
        fields(
            persistent,
            (
                "lookups",
                "misses",
                "route_hits",
                "apply_hits",
                "requested_root_hits",
                "intermediate_hits",
            ),
            "invalid persistent usage counters",
        )
        require(
            all(integer(value, 0, U64_MAX) for value in persistent.values()),
            "invalid persistent usage counter",
        )
        records = dispatch["records"]
        require(isinstance(records, list), "invalid usage records")
        counts = {}
        for record in records:
            fields(record, ("work", "backing_hits"), "invalid usage record")
            key = work(record["work"], arity)
            require(
                key not in counts and integer(record["backing_hits"], 1, U64_MAX),
                "duplicate or nonpositive usage record",
            )
            counts[key] = record["backing_hits"]
            result[key] = checked_sum((result[key], record["backing_hits"]))
        route = checked_sum(count for key, count in counts.items() if key[0] == "route")
        apply = checked_sum(count for key, count in counts.items() if key[0] == "apply")
        hits = checked_sum((route, apply))
        require(
            route == persistent["route_hits"]
            and apply == persistent["apply_hits"]
            and hits
            == checked_sum(
                (persistent["requested_root_hits"], persistent["intermediate_hits"])
            )
            and persistent["misses"] <= persistent["lookups"]
            and hits == persistent["lookups"] - persistent["misses"],
            "usage dispatch hit frequencies do not reconcile",
        )
    return result


def embedded_eligibility(profile):
    rows = profile["eligibility_documents"]
    require(isinstance(rows, list) and rows, "missing public eligibility inventories")
    documents = {}
    held_out_ids, held_out_inputs = set(), set()
    for row in rows:
        fields(
            row,
            ("sha256", "json_bytes_base64"),
            "invalid embedded eligibility document",
        )
        require(
            hash256(row["sha256"]) and isinstance(row["json_bytes_base64"], str),
            "invalid embedded eligibility identity",
        )
        try:
            raw = base64.b64decode(row["json_bytes_base64"], validate=True)
        except (ValueError, TypeError) as error:
            raise ValueError("invalid embedded eligibility encoding") from error
        require(
            hashlib.sha256(raw).hexdigest() == row["sha256"]
            and row["sha256"] not in documents,
            "embedded public inventory SHA256 differs or repeats",
        )
        document = decode_json(raw)
        require(
            isinstance(document, dict), "public eligibility inventory must be an object"
        )
        documents[row["sha256"]] = document
        held_out = document.get("held_out", [])
        require(isinstance(held_out, list), "invalid frozen held-out inventory")
        for case in held_out:
            require(
                isinstance(case, dict)
                and isinstance(case.get("id"), str)
                and case["id"],
                "invalid frozen held-out inventory",
            )
            held_out_ids.add(case["id"])
            if isinstance(case.get("public_input"), str):
                held_out_inputs.add(
                    hashlib.sha256(case["public_input"].encode()).hexdigest()
                )
    return documents, held_out_ids, held_out_inputs


def physical_case(root, case, document, pointer):
    require(
        pointer == "/cases/0"
        and case["role"] == "physical-example"
        and isinstance(document.get("cases"), list)
        and len(document["cases"]) == 1,
        "physical inventory does not authorize this input role",
    )
    selected = document["cases"][0]
    require(
        isinstance(selected, dict)
        and selected.get("id")
        == case["case_id"]
        == selected.get("source_job_id")
        == "q0"
        and selected.get("role") == "physical-example"
        and selected.get("projection") == "zero-momentum-metric"
        and selected.get("definition") == "massless-qcd-four-rung-native-uv-v1"
        and selected.get("input_source_kind")
        == "prepared-vakint-input.symbolica-file-bytes"
        and hash256(selected.get("source_job_config_sha256"))
        and selected.get("public_input_source_sha256")
        == case["public_input_source_sha256"]
        and integer(selected.get("public_input_source_bytes"), 1, U64_MAX),
        "physical eligibility must preserve the complete zero-momentum fixture",
    )
    embedded = embedded_eligibility(
        {"eligibility_documents": document.get("prepared_manifest_documents")}
    )[0]
    prepared = embedded.get(selected.get("prepared_manifest_sha256"), {})
    path = data.checked_path(root, "5L/benchmarks/zero-momentum/prepared-input.json")
    require(
        path.is_file()
        and data.digest(path) == selected["prepared_manifest_sha256"]
        and prepared.get("schema") == "vakint.qcd-ladder.prepared-input.v1"
        and prepared.get("projection") == selected["projection"]
        and prepared.get("definition") == selected["definition"]
        and prepared.get("input")
        == {
            "sha256": selected["public_input_source_sha256"],
            "bytes": selected["public_input_source_bytes"],
        }
        and isinstance(prepared.get("scientific_sources_sha256"), dict)
        and set(prepared["scientific_sources_sha256"])
        == {
            "ladder.dot",
            "phi3.json",
            "physical.rs",
            "projector.rs",
            "qcd.json",
            "vacuum.rs",
        }
        and all(
            hash256(value) for value in prepared["scientific_sources_sha256"].values()
        )
        and hash256(prepared.get("scientific_assembly_sha256")),
        "physical public input differs from the authenticated prepared source",
    )
    return selected, prepared


def public_case(root, case, documents, held_out_ids, held_out_inputs):
    evidence = case["role_evidence"]
    fields(
        evidence, ("document_sha256", "json_pointer"), "invalid public role evidence"
    )
    require(hash256(evidence["document_sha256"]), "invalid public inventory SHA256")
    document = documents.get(evidence["document_sha256"])
    require(document is not None, "unknown public eligibility inventory")
    pointer = evidence["json_pointer"]
    require(isinstance(pointer, str), "invalid public case pointer")
    if document.get("schema") == "vakint.physical-cache-usage-source-inventory.v1":
        physical_case(root, case, document, pointer)
        require(
            case["case_id"] not in held_out_ids
            and case["public_input_source_sha256"] not in held_out_inputs,
            "held-out physical input cannot select cache records",
        )
        return evidence["document_sha256"]
    parts = pointer.split("/")
    require(
        document.get("schema")
        in (
            "vakint.five-loop-cache-workload.v1",
            "vakint.five-loop-frozen-public-suites.v1",
        )
        and len(parts) == 3
        and parts[0] == ""
        and parts[1] == "tuning"
        and re.fullmatch(r"0|[1-9][0-9]*", parts[2]) is not None
        and case["role"] == "tuning",
        "public inventory does not authorize this input role",
    )
    tuning = document.get("tuning")
    index = int(parts[2])
    require(
        isinstance(tuning, list) and index < len(tuning),
        "public case pointer is absent",
    )
    selected = tuning[index]
    require(
        isinstance(selected, dict)
        and selected.get("id") == case["case_id"]
        and isinstance(selected.get("public_input"), str),
        "public case identity differs",
    )
    source = hashlib.sha256(selected["public_input"].encode()).hexdigest()
    require(
        source == case["public_input_source_sha256"]
        and case["case_id"] not in held_out_ids
        and source not in held_out_inputs,
        "held-out or mismatched public input cannot select cache records",
    )
    return evidence["document_sha256"]


def cohort_ids(value):
    require(isinstance(value, dict), "missing usage compiled cohort")
    for name in COHORT_FIELDS:
        item = value.get(name)
        require(
            bool(re.fullmatch(r"[0-9a-f]{40}", item))
            if name.endswith("revision") and isinstance(item, str)
            else hash256(item),
            "invalid usage compiled cohort identity",
        )


def cohort(root, value):
    cohort_ids(value)
    require(
        all(
            hash256(value.get(name))
            for name in ("measurement_executable_sha256", "collector_source_sha256")
        )
        and all(
            isinstance(value.get(name), str) and value[name]
            for name in ("profile", "rustc")
        ),
        "usage cohort lacks actual collector/compiler identity",
    )
    references = {}
    for name in (
        "collector_artifacts",
        "main_source_snapshot",
        "native_source_snapshot",
    ):
        reference = value.get(name)
        fields(
            reference,
            ("path_hint", "sha256"),
            "usage cohort lacks portable source proof",
        )
        references[name] = source_json(
            root, {"path": reference["path_hint"], "sha256": reference["sha256"]}
        )
    artifacts = references["collector_artifacts"]
    require(isinstance(artifacts, dict), "invalid collector artifact proof")
    binaries = artifacts.get("artifacts", {})
    require(isinstance(binaries, dict), "invalid collector artifact inventory")
    collector = value.get("collector", "measure_cache")
    require(
        isinstance(collector, str)
        and collector in ("measure_cache", "five_loop_qcd_ladder"),
        "unknown usage collector",
    )
    measure = binaries.get(collector, {})
    stamps = artifacts.get("compile_proof", {})
    require(
        isinstance(measure, dict) and isinstance(stamps, dict),
        "invalid collector compile proof",
    )
    require(
        artifacts.get("status") == "BUILT_AND_ALL_FIVE_STAMPS_AUTHENTICATED"
        and artifacts.get("source_head") == value["main_revision"]
        and artifacts.get("profile") == value["profile"]
        and all(
            stamps.get(stamp) == value[name] for name, stamp in COHORT_FIELDS.items()
        )
        and stamps.get("VAKINT_CACHE_BUILD_PROFILE") == value["profile"]
        and stamps.get("VAKINT_CACHE_BUILD_RUSTC") == value["rustc"]
        and measure.get("sha256") == value["measurement_executable_sha256"]
        and measure.get("all_five_actual_env_dep_stamps")
        == {stamp: value[name] for name, stamp in COHORT_FIELDS.items()},
        "usage collector differs from its actual compiled artifact proof",
    )
    for name, revision, checksum in (
        ("main_source_snapshot", "main_revision", "main_source_snapshot_sha256"),
        ("native_source_snapshot", "native_revision", "native_source_snapshot_sha256"),
    ):
        require(
            isinstance(references[name], dict)
            and references[name].get("schema")
            == "vakint.actual-tracked-source-snapshot.v1"
            and value[name]["sha256"] == value[checksum]
            and references[name].get("revision") == value[revision],
            "usage source inventory differs from compiled source stamp",
        )
    files = references["main_source_snapshot"].get("files", {})
    require(isinstance(files, dict), "invalid compiled source inventory")
    collector_source = files.get(f"crates/vakint/examples/{collector}.rs", {})
    require(
        isinstance(collector_source, dict)
        and collector_source.get("sha256") == value["collector_source_sha256"],
        "usage collector source differs from its compiled source inventory",
    )
    if collector == "five_loop_qcd_ladder":
        helpers = value.get("collector_helper_sources_sha256")
        require(
            isinstance(helpers, dict)
            and set(helpers) == PHYSICAL_COLLECTOR_HELPERS
            and all(
                hash256(checksum)
                and isinstance(files.get(path), dict)
                and files[path].get("sha256") == checksum
                for path, checksum in helpers.items()
            ),
            "physical collector helpers differ from the compiled source inventory",
        )


def profile_data(root, profile, directory):
    references = profile["compiled_cohort"].get("data_manifests")
    fields(
        references,
        ("root", "loop", "application"),
        "usage needs original data manifest proofs",
    )
    documents = {}
    for name, field in (
        ("root", "root_manifest_sha256"),
        ("loop", "loop_manifest_sha256"),
        ("application", "application_sha256"),
    ):
        reference = references[name]
        fields(
            reference, ("path_hint", "sha256"), "invalid original data proof reference"
        )
        require(
            reference["sha256"] == profile["data"][field],
            "usage data proof SHA differs",
        )
        documents[name] = source_json(
            root, {"path": reference["path_hint"], "sha256": reference["sha256"]}
        )
    release, loop = documents["root"], documents["loop"]
    require(
        isinstance(release, dict)
        and release.get("schema") == data.ROOT_SCHEMA
        and isinstance(release.get("version"), str)
        and isinstance(release.get("loop_packs"), list),
        "invalid original data root authority",
    )
    packs = [
        row
        for row in release["loop_packs"]
        if isinstance(row, dict)
        and type(row.get("loop_count")) is int
        and row["loop_count"] == 5
    ]
    require(
        len(packs) == 1
        and packs[0].get("manifest") == "5L/manifest.json"
        and packs[0].get("manifest_sha256") == profile["data"]["loop_manifest_sha256"]
        and isinstance(loop, dict)
        and loop.get("schema") == data.LOOP_SCHEMA
        and type(loop.get("loop_count")) is int
        and loop["loop_count"] == 5
        and loop.get("version") == release.get("version")
        and isinstance(loop.get("files"), dict),
        "original root does not authenticate the five-loop data manifest",
    )
    application = source_file(
        root,
        {
            "path": references["application"]["path_hint"],
            "sha256": references["application"]["sha256"],
        },
    )
    require(
        same(loop["files"].get("ibps/application.json"), data.file_record(application))
        and data.digest(directory / "ibps/application.json")
        == profile["data"]["application_sha256"],
        "original loop does not authenticate the active application bytes",
    )


def native_artifact(root, raw):
    artifact = source_json(root, raw.get("collector_artifacts"))
    require(
        isinstance(artifact, dict)
        and artifact.get("schema")
        == "vakint.native-selected-cache-producer-artifact.v1",
        "invalid Native exporter artifact proof",
    )
    compiled = raw["compiled_cohort"]
    stamps, binary = artifact.get("stamps"), artifact.get("binary")
    gates = artifact.get("gates", {})
    require(
        isinstance(stamps, dict)
        and isinstance(binary, dict)
        and artifact.get("state")
        == "PASS_BUILD_PARSER_CLIPPY_BUILDINFO_NO_5L_ACTIVATION"
        and isinstance(gates, dict)
        and all(
            isinstance(gates.get(name), dict)
            and type(gates[name].get("exit_code")) is int
            and gates[name]["exit_code"] == 0
            for name in ("parser-tests", "clippy", "build", "build-info")
        )
        and same(compiled, artifact.get("compiled_cohort"))
        and all(
            stamps.get(stamp) == compiled[name] for name, stamp in COHORT_FIELDS.items()
        )
        and binary.get("ELF") is True
        and integer(binary.get("bytes"), 1, U64_MAX)
        and binary.get("sha256")
        == raw["executable_sha256"]
        == compiled.get("measurement_executable_sha256")
        and artifact.get("source_unchanged") is True
        and artifact.get("native_and_kernel_clean") is True,
        "Native exporter cohort or ELF differs from actual artifact proof",
    )
    identity = compiled.get("source_identity")
    require(
        isinstance(identity, dict)
        and identity.get("schema") == "native.private-layered-helper-source-identity.v1"
        and isinstance(identity.get("files"), dict),
        "Native exporter lacks actual layered source identity",
    )
    native = identity.get("native_identity")
    require(
        hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        == compiled["main_source_snapshot_sha256"]
        and isinstance(native, dict)
        and native.get("schema") == "native.git-source-tree-identity.v1"
        and native.get("clean") is True
        and type(native.get("codec_state_format")) is int
        and native["codec_state_format"] == 6
        and native.get("revision") == compiled["native_revision"]
        and native.get("kernel_revision") == compiled["kernel_revision"]
        and hashlib.sha256(
            json.dumps(native, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        == compiled["native_source_snapshot_sha256"],
        "Native exporter source or kernel identity differs from compiled stamps",
    )
    reference = artifact.get("source_freeze")
    fields(
        reference,
        ("path", "bytes", "sha256"),
        "Native exporter lacks its archived source freeze",
    )
    path = source_file(root, {name: reference[name] for name in ("path", "sha256")})
    require(
        integer(reference["bytes"], 1, U64_MAX)
        and path.stat().st_size == reference["bytes"],
        "Native exporter source freeze length differs",
    )
    freeze = source_json(root, {name: reference[name] for name in ("path", "sha256")})
    require(
        isinstance(freeze, dict)
        and isinstance(freeze.get("files"), dict)
        and set(identity["files"]) <= set(freeze["files"])
        and identity["files"],
        "Native exporter source inventory differs",
    )
    for name, row in freeze["files"].items():
        fields(row, ("path", "bytes", "sha256"), "invalid archived Native source file")
        require(
            hash256(row["sha256"])
            and (
                name not in identity["files"]
                or row["sha256"] == identity["files"][name]
            )
            and integer(row["bytes"], 0, U64_MAX),
            "archived Native source identity differs",
        )
        source = source_file(root, {field: row[field] for field in ("path", "sha256")})
        require(
            source.stat().st_size == row["bytes"],
            "archived Native source length differs",
        )
    require(
        identity["files"].get("src/main.rs") == compiled.get("collector_source_sha256"),
        "Native exporter main source differs",
    )


def native_index_identity(value):
    fields(
        value,
        ("schema", "layout", "indexes", "sha256"),
        "invalid Native index identity",
    )
    require(
        value["schema"] == "vakint.native-cache-index-identity.v1"
        and value["layout"] in ("bundle", "pack")
        and hash256(value["sha256"]),
        "invalid Native index identity header",
    )
    indexes = value["indexes"]
    require(isinstance(indexes, dict) and indexes, "empty Native index identity")
    for name, row in indexes.items():
        require(
            isinstance(name, str)
            and (
                name in ("cache.rrindex", "bundle.rrindex")
                or re.fullmatch(r"bindings/[0-9a-f]{64}/cache\.rrindex", name)
            ),
            "unsafe Native index identity path",
        )
        fields(row, ("bytes", "sha256"), "invalid Native index file identity")
        require(
            integer(row["bytes"], 1, U64_MAX) and hash256(row["sha256"]),
            "invalid Native index file bytes or hash",
        )
    require(
        set(indexes) == {"cache.rrindex"}
        if value["layout"] == "pack"
        else "bundle.rrindex" in indexes
        and "cache.rrindex" not in indexes
        and len(indexes) > 1,
        "Native index layout differs",
    )
    document = {name: value[name] for name in ("schema", "layout", "indexes")}
    require(
        hashlib.sha256(
            json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        == value["sha256"],
        "Native index commitment differs",
    )


def referenced_json(root, reference):
    fields(reference, ("path_hint", "sha256"), "invalid physical run reference")
    return source_json(
        root, {"path": reference["path_hint"], "sha256": reference["sha256"]}
    )


def physical_receipt(root, case, profile, documents, receipt):
    """Project an authenticated physical run into the common usage checks.

    Supervision and normal/diagnostic parity are separate source evidence. The
    collector neither attests to its own exit nor invents a text Workload.
    """
    fields(
        receipt,
        (
            "schema",
            "benchmark",
            "completion",
            "launch",
            "reference_benchmark",
            "reference_completion",
            "reference_launch",
        ),
        "invalid physical usage receipt fields",
    )
    compiled = profile["compiled_cohort"]
    require(
        case["role"] == "physical-example"
        and compiled.get("collector") == "five_loop_qcd_ladder",
        "physical usage requires its actual physical collector",
    )
    authority = documents.get(case["role_evidence"]["document_sha256"], {})
    selected, prepared = physical_case(
        root, case, authority, case["role_evidence"]["json_pointer"]
    )
    reports, processes, commands = [], [], []
    for prefix, diagnostic in (("reference_", False), ("", True)):
        report = referenced_json(root, receipt[prefix + "benchmark"])
        completion = referenced_json(root, receipt[prefix + "completion"])
        launch = referenced_json(root, receipt[prefix + "launch"])
        require(
            all(isinstance(value, dict) for value in (report, completion, launch)),
            "invalid physical run evidence",
        )
        identity = report.get("prepared_input", {})
        sources = report.get("consumer_fixture_sources_sha256", {})
        require(
            report.get("schema") == "vakint.qcd-ladder.benchmark.v1"
            and report.get("projection") == "zero-momentum-metric"
            and report.get("input_mode") == "prepared"
            and report.get("fresh_native_preparation") is False
            and isinstance(identity, dict)
            and identity.get("manifest_sha256") == selected["prepared_manifest_sha256"]
            and same(identity.get("manifest"), prepared)
            and report.get("input_sha256")
            == report.get("input_canonical_sha256")
            == case["input_sha256"]
            == case["public_input_source_sha256"]
            and type(report.get("input_bytes")) is int
            and report["input_bytes"] == selected["public_input_source_bytes"]
            and isinstance(sources, dict)
            and set(sources) == set(prepared["scientific_sources_sha256"]) | {"mod.rs"}
            and all(hash256(value) for value in sources.values())
            and all(
                sources[name] == value
                for name, value in prepared["scientific_sources_sha256"].items()
            ),
            "physical run differs from the complete canonical prepared input",
        )
        require(
            report.get("master_mode") == "retain"
            and report.get("guard_policy") == "canonical-full-sorted-deduplicated"
            and report.get("retained_result_available") is True
            and report.get("reduction_completed") is True
            and report.get("reduction_error") is None
            and report.get("cache_hit_diagnostic_enabled") is diagnostic
            and report.get("diagnostic_only") is diagnostic
            and report.get("performance_claim") is False
            and report.get("warm_requested") is False
            and report.get("running_cache_path") is None
            and report.get("running_cache_attached") is False
            and report.get("running_cache_capture_only") is False
            and report.get("persistent_cache_attached") is True
            and report.get("persistent_cache_policy") == "manual-five-loop-only"
            and same(
                report.get("persistent_cache_attachments_before"),
                {str(i): False for i in range(1, 6)},
            )
            and same(
                report.get("persistent_cache_attachments_during_evaluation"),
                {str(i): i == 5 for i in range(1, 6)},
            ),
            "physical usage requires one retained read-only cached evaluation",
        )
        actual_cohort = report.get("compiled_cohort", {})
        # Exported Nix binaries may retain a source path without .git. The
        # authenticated compiled source stamps above are the authority; these
        # optional runtime probes must still be consistent and never dirty.
        runtime_revision, runtime_dirty = (
            report.get("source_commit"),
            report.get("source_dirty"),
        )
        require(
            isinstance(actual_cohort, dict)
            and all(
                actual_cohort.get(name) == compiled[name]
                for name in (*COHORT_FIELDS, "profile", "rustc")
            )
            and report.get("executable_sha256")
            == compiled["measurement_executable_sha256"]
            and report.get("collector_source_sha256")
            == compiled["collector_source_sha256"]
            and same(
                report.get("collector_helper_sources_sha256"),
                compiled["collector_helper_sources_sha256"],
            )
            and "source_commit" in report
            and "source_dirty" in report
            and (
                (runtime_revision is None and runtime_dirty is None)
                or (
                    runtime_revision == compiled["main_revision"]
                    and runtime_dirty is False
                )
            )
            and report.get("data_manifest_sha256")
            == profile["data"]["root_manifest_sha256"]
            and same(report.get("cache_identity"), case["cache_identity"])
            and same(report.get("cache_identity_after"), case["cache_identity"]),
            "physical run cohort, data or immutable cache identity differs",
        )
        closure, guards = report.get("catalogue_closure", {}), report.get("guards", {})
        statistics = report.get("saved_application_cache", {})
        require(
            isinstance(closure, dict)
            and closure.get("closed") is True
            and type(closure.get("unknown_count")) is int
            and closure["unknown_count"] == 0
            and closure.get("unknown_preview") == []
            and hash256(closure.get("unknown_sha256"))
            and isinstance(guards, dict)
            and integer(guards.get("count"), 0, U64_MAX)
            and guards.get("includes_preparation_conditions") is True
            and guards.get("sha256") == case["guards_sha256"]
            and report.get("result_sha256") == case["value_sha256"]
            and integer(report.get("result_bytes"), 1, U64_MAX),
            "physical result, complete guards or catalogue closure differs",
        )
        require(
            isinstance(statistics, dict)
            and statistics.get("read_backing") is True
            and statistics.get("running") is None
            and same(statistics.get("binding"), profile["semantic_binding"])
            and isinstance(statistics.get("persistent"), dict)
            and all(
                type(statistics["persistent"].get(name)) is int
                and statistics["persistent"][name] == 0
                for name in ("captured_records", "skipped_records")
            ),
            "physical usage must not capture or skip persistent records",
        )
        process, supervisor = launch.get("collector", {}), launch.get("supervisor", {})
        require(
            all(
                isinstance(value, dict)
                and integer(value.get("pid"), 1, U64_MAX)
                and integer(value.get("start_ticks"), 1, U64_MAX)
                for value in (process, supervisor)
            )
            and process["pid"] != supervisor["pid"]
            and same(completion.get("collector"), process)
            and completion.get("collector_exit_code") == 0
            and type(completion.get("collector_exit_code")) is int
            and completion.get("process_zero_acceptance") is True
            and completion.get("functional_acceptance") is True
            and completion.get("native_child_restarted_or_signalled") is False
            and completion.get("authoritative_wait_error") is None
            and completion.get("acceptance_error") is None
            and completion.get("performance_eligible") is False
            and launch.get("performance_eligible") is False
            and launch.get("automatic_retry") is False
            and launch.get("runtime_hard_cap") is None
            and hash256(launch.get("config_sha256"))
            and launch["config_sha256"] == completion.get("config_sha256"),
            "physical usage lacks accepted actual process supervision",
        )
        argv, executable = launch.get("argv"), completion.get("post_executable", {})
        require(
            isinstance(argv, list)
            and argv
            and all(isinstance(arg, str) for arg in argv)
            and argv[0].startswith("/")
            and isinstance(executable, dict)
            and executable.get("path") == argv[0]
            and executable.get("sha256") == report["executable_sha256"]
            and integer(executable.get("bytes"), 1, U64_MAX)
            and argv.count("--classify-cache-hits") == int(diagnostic)
            and argv.count("--work-dir") == 1
            and "--cache" in argv
            and "--prepared-input" in argv
            and "--warm" not in argv
            and not any(arg.startswith("--running-cache") for arg in argv),
            "physical launch differs from its executable or diagnostic policy",
        )
        command = [arg for arg in argv if arg != "--classify-cache-hits"]
        index = command.index("--work-dir")
        require(index + 1 < len(command), "physical launch lacks its output path")
        del command[index : index + 2]
        commands.append(command)
        outputs, artifacts = (
            completion.get("outputs", {}),
            completion.get("terminal_artifacts", {}),
        )
        expected = {
            "benchmark.json": receipt[prefix + "benchmark"]["sha256"],
            "result.symbolica": report["result_sha256"],
            "nonzero-conditions.symbolica": guards["sha256"],
            "unknown-masters.json": closure["unknown_sha256"],
        }
        benchmark_file = source_file(
            root,
            {
                "path": receipt[prefix + "benchmark"]["path_hint"],
                "sha256": receipt[prefix + "benchmark"]["sha256"],
            },
        )
        require(
            isinstance(outputs, dict)
            and isinstance(artifacts, dict)
            and all(
                isinstance(artifacts.get(name), dict)
                and artifacts[name].get("exists") is True
                and integer(
                    artifacts[name].get("bytes"),
                    0 if name == "nonzero-conditions.symbolica" else 1,
                    U64_MAX,
                )
                and artifacts[name].get("sha256") == checksum
                for name, checksum in expected.items()
            )
            and outputs.get("benchmark_sha256") == expected["benchmark.json"]
            and outputs.get("result_sha256") == report["result_sha256"]
            and type(outputs.get("result_bytes")) is int
            and outputs["result_bytes"] == report["result_bytes"]
            and outputs.get("guards_sha256") == guards["sha256"]
            and type(outputs.get("guards_count")) is int
            and outputs["guards_count"] == guards["count"]
            and outputs.get("unknown_sha256") == closure["unknown_sha256"]
            and type(outputs.get("unknown_count")) is int
            and outputs["unknown_count"] == 0
            and artifacts["result.symbolica"]["bytes"] == report["result_bytes"]
            and artifacts["benchmark.json"]["bytes"] == benchmark_file.stat().st_size,
            "physical completion does not bind the complete retained files",
        )
        reports.append(report)
        processes.append((process["pid"], process["start_ticks"]))
    reference, report = reports
    require(
        processes[0] != processes[1]
        and commands[0] == commands[1]
        and same(
            reference["consumer_fixture_sources_sha256"],
            report["consumer_fixture_sources_sha256"],
        )
        and reference["source_commit"] == report["source_commit"]
        and reference["source_dirty"] is report["source_dirty"]
        and isinstance(report.get("cache_file_options"), dict)
        and same(reference.get("cache_file_options"), report["cache_file_options"])
        and same(reference.get("families"), report.get("families"))
        and isinstance(report.get("families"), dict)
        and report["families"]
        and reference["result_bytes"] == report["result_bytes"]
        and reference["guards"]["count"] == report["guards"]["count"]
        and reference["catalogue_closure"]["unknown_sha256"]
        == report["catalogue_closure"]["unknown_sha256"]
        and reference.get("cache_hit_diagnostic") is None,
        "physical usage requires a fresh same-cohort normal reference with exact parity",
    )
    return {
        "success": True,
        "worker_success": True,
        "fresh_process": True,
        "case_id": case["case_id"],
        "variant": "cached",
        "supervision": {"success": True, "exit_code": 0, "deadline_exhausted": False},
        "input_sha256": report["input_canonical_sha256"],
        "value_sha256": report["result_sha256"],
        "guards_sha256": report["guards"]["sha256"],
        "identity": {
            "data_manifest_sha256": report["data_manifest_sha256"],
            "executable_sha256": report["executable_sha256"],
            "compiled_driver_sha256": report["collector_source_sha256"],
            "build_git_revision": report["compiled_cohort"]["main_revision"],
            "build_profile": report["compiled_cohort"]["profile"],
            "build_rustc": report["compiled_cohort"]["rustc"],
            **report["cache_identity"],
            "cache_hit_diagnostic": True,
        },
        "cache_statistics": report.get("saved_application_cache"),
        "cache_hit_diagnostic": report.get("cache_hit_diagnostic"),
    }


def case_receipt(root, case, profile, documents):
    reference = case["receipt"]
    require(
        isinstance(reference, dict) and set(reference) <= {"sha256", "path_hint"},
        "invalid accepted case receipt",
    )
    receipt = source_json(
        root, {"path": reference.get("path_hint"), "sha256": reference.get("sha256")}
    )
    require(isinstance(receipt, dict), "accepted case receipt must be an object")
    compiled = profile["compiled_cohort"]
    if receipt.get("schema") == "vakint.physical-cache-usage-receipt.v1":
        receipt = physical_receipt(root, case, profile, documents, receipt)
    else:
        identity = receipt.get("identity", {})
        require(
            compiled.get("collector", "measure_cache") == "measure_cache"
            and isinstance(identity, dict)
            and hash256(identity.get("workload_sha256")),
            "invalid accepted case identity",
        )
        invocation = documents.get(identity.get("workload_sha256"), {})
        tuning = invocation.get("tuning", [])
        require(isinstance(tuning, list), "invalid invocation tuning inventory")
        actual = [
            row
            for row in tuning
            if isinstance(row, dict) and row.get("id") == case["case_id"]
        ]
        require(
            invocation.get("schema") == "vakint.five-loop-cache-workload.v1"
            and len(actual) == 1
            and isinstance(actual[0].get("public_input"), str)
            and hashlib.sha256(actual[0]["public_input"].encode()).hexdigest()
            == case["public_input_source_sha256"],
            "accepted invocation workload differs from authorized public source",
        )
    identity = receipt["identity"]
    supervision = receipt.get("supervision", {})
    require(
        isinstance(supervision, dict)
        and receipt.get("success") is True
        and receipt.get("worker_success") is True
        and receipt.get("fresh_process") is True
        and supervision.get("success") is True
        and type(receipt["supervision"].get("exit_code")) is int
        and receipt["supervision"]["exit_code"] == 0
        and receipt["supervision"].get("deadline_exhausted") is False
        and receipt.get("case_id") == case["case_id"]
        and receipt.get("variant") == "cached"
        and identity.get("cache_hit_diagnostic") is True
        and case["guard_policy"] == "canonical-full-sorted-deduplicated",
        "usage requires a completed successful accepted case",
    )
    statistics = receipt.get("cache_statistics", {})
    require(
        isinstance(statistics, dict)
        and all(
            receipt.get(name) == case[name]
            for name in ("input_sha256", "value_sha256", "guards_sha256")
        )
        and identity.get("data_manifest_sha256")
        == profile["data"]["root_manifest_sha256"]
        and identity.get("executable_sha256")
        == compiled["measurement_executable_sha256"]
        and identity.get("compiled_driver_sha256")
        == compiled["collector_source_sha256"]
        and identity.get("build_git_revision") == compiled["main_revision"]
        and identity.get("build_profile") == compiled["profile"]
        and identity.get("build_rustc") == compiled["rustc"]
        and same(statistics.get("binding"), profile["semantic_binding"]),
        "usage case input/data/collector/binding differs",
    )
    projection = {
        name: identity.get(name)
        for name in ("cache_sha256", "cache_native_index_identity")
    }
    fields(
        case["cache_identity"],
        ("cache_sha256", "cache_native_index_identity"),
        "invalid usage cache identity projection",
    )
    require(
        same(case["cache_identity"], projection)
        and (
            hash256(projection["cache_sha256"])
            and projection["cache_native_index_identity"] is None
            or projection["cache_sha256"] is None
            and isinstance(projection["cache_native_index_identity"], dict)
        ),
        "usage case persistent cache identity differs",
    )
    if projection["cache_native_index_identity"] is not None:
        native_index_identity(projection["cache_native_index_identity"])
    diagnostic = receipt.get("cache_hit_diagnostic", {})
    require(
        isinstance(diagnostic, dict)
        and diagnostic.get("stream_complete") is True
        and diagnostic.get("diagnostic_only") is True
        and type(diagnostic.get("interval_ns")) is int
        and diagnostic["interval_ns"] == 0
        and diagnostic.get("error") is None
        and diagnostic.get("sha256") == case["trace"]["sha256"],
        "usage lacks its complete accepted lossless trace",
    )
    persistent = statistics.get("persistent", {})
    require(
        isinstance(persistent, dict)
        and all(
            type(persistent.get(name)) is int
            and persistent[name]
            == checked_sum(
                dispatch["persistent"][name] for dispatch in case["dispatches"]
            )
            for name in (
                "lookups",
                "misses",
                "route_hits",
                "apply_hits",
                "requested_root_hits",
                "intermediate_hits",
            )
        ),
        "usage dispatch totals differ from accepted Native statistics",
    )
    proven = identity.get("owner_proof", {})
    if isinstance(proven, dict) and isinstance(proven.get("compiled_cohort"), dict):
        require(
            all(
                proven["compiled_cohort"].get(name) == compiled[name]
                for name in COHORT_FIELDS
            ),
            "usage source stamps differ from accepted owner proof",
        )


def profile_frequencies(root, profile, selected, binding):
    fields(
        profile,
        (
            "schema",
            "semantic_binding",
            "compiled_cohort",
            "data",
            "eligibility_documents",
            "cases",
        ),
        "invalid usage profile fields",
    )
    require(
        profile["schema"] == "vakint.cache-record-usage-profile.v1"
        and same(profile["semantic_binding"], binding),
        "usage profile binding differs",
    )
    cohort(root, profile["compiled_cohort"])
    fields(
        profile["data"],
        ("root_manifest_sha256", "loop_manifest_sha256", "application_sha256"),
        "invalid usage data bindings",
    )
    require(
        all(hash256(value) for value in profile["data"].values()),
        "invalid usage data identity",
    )
    documents, held_out_ids, held_out_inputs = embedded_eligibility(profile)
    cases = profile["cases"]
    require(isinstance(cases, list) and cases, "empty eligible usage profile")
    requested = selected["eligible_case_ids"]
    require(
        isinstance(requested, list)
        and requested
        and all(isinstance(name, str) and name for name in requested)
        and len(set(requested)) == len(requested),
        "invalid selected eligible case IDs",
    )
    all_ids, frequencies = set(), collections.Counter()
    for case in cases:
        fields(
            case,
            (
                "case_id",
                "role",
                "input_sha256",
                "public_input_source_sha256",
                "role_evidence",
                "receipt",
                "trace",
                "cache_identity",
                "value_sha256",
                "guards_sha256",
                "guard_policy",
                "observer_status",
                "interval_ns",
                "input_dispatch_count",
                "dispatches",
            ),
            "invalid usage case fields",
        )
        require(
            isinstance(case["case_id"], str)
            and case["case_id"]
            and case["case_id"] not in all_ids,
            "duplicate or invalid usage case ID",
        )
        all_ids.add(case["case_id"])
        require(
            all(
                hash256(case[name])
                for name in (
                    "input_sha256",
                    "public_input_source_sha256",
                    "value_sha256",
                    "guards_sha256",
                )
            ),
            "invalid usage case hash",
        )
        require(
            case["observer_status"] == "Active"
            and type(case["interval_ns"]) is int
            and case["interval_ns"] == 0
            and case["guard_policy"]
            in ("native-ordered-vector", "canonical-full-sorted-deduplicated"),
            "usage observer is incomplete or sampled",
        )
        require(
            isinstance(case["trace"], dict)
            and set(case["trace"]) <= {"sha256", "path_hint"}
            and hash256(case["trace"].get("sha256")),
            "invalid bound usage trace",
        )
        public_case(root, case, documents, held_out_ids, held_out_inputs)
        counts = dispatch_frequencies(case, binding["physical_arity"])
        case_receipt(root, case, profile, documents)
        if case["case_id"] in requested:
            for key, count in counts.items():
                frequencies[key] = checked_sum((frequencies[key], count))
    require(set(requested) <= all_ids, "selected usage names an unknown case")
    return frequencies


def composed_profile_frequencies(
    root, profile, selected, binding, directory, source, manifest
):
    """Join authenticated v1 observations, keeping each real collector identity.

    Member validators remain the v1 authority. Composition adds common-source,
    settings, global holdout and non-duplication checks; it never replays traces
    or constructs a fictitious aggregate collector/executable.
    """
    fields(
        profile,
        ("schema", "semantic_binding", "common", "members"),
        "invalid composed usage profile fields",
    )
    require(
        profile["schema"] == PROFILE_V2_SCHEMA
        and same(profile["semantic_binding"], binding),
        "composed usage profile binding differs",
    )
    common = profile["common"]
    fields(
        common,
        (
            "source_cache_native_index_identity",
            "data",
            "compiled_source_cohort",
            "raw_reduction_settings",
            "output_conventions",
            "held_out_authority_sha256",
        ),
        "invalid composed usage common fields",
    )
    fields(
        common["data"],
        ("root_manifest_sha256", "loop_manifest_sha256", "application_sha256"),
        "invalid composed usage data",
    )
    index = source["cache_native_index_identity"]
    native_index_identity(common["source_cache_native_index_identity"])
    require(
        same(common["source_cache_native_index_identity"], index),
        "composed usage differs from selected cumulative index",
    )
    require(
        common["data"].get("root_manifest_sha256") == source["data_manifest_sha256"],
        "composed usage data differs from cumulative producer",
    )
    compiled = common["compiled_source_cohort"]
    fields(compiled, COMMON_COHORT_FIELDS, "invalid common compiled source cohort")
    cohort_ids(compiled)
    require(
        hash256(common["held_out_authority_sha256"]),
        "invalid common frozen held-out authority",
    )
    snapshot = referenced_json(root, compiled["main_source_snapshot"])
    require(
        isinstance(snapshot, dict) and isinstance(snapshot.get("files"), dict),
        "invalid common compiled source inventory",
    )
    frozen = snapshot.get("files", {}).get(
        "crates/vakint/examples/build_cache/frozen-public-suites.json", {}
    )
    require(
        isinstance(frozen, dict)
        and frozen.get("sha256") == common["held_out_authority_sha256"],
        "common held-out authority differs from compiled frozen suites",
    )
    members = profile["members"]
    require(isinstance(members, list) and members, "empty composed usage profile")
    requested = selected["eligible_case_ids"]
    require(
        isinstance(requested, list)
        and requested
        and all(isinstance(name, str) and name for name in requested)
        and len(set(requested)) == len(requested),
        "invalid composed selected eligible case IDs",
    )
    member_ids, profile_hashes, case_ids, receipt_hashes = set(), set(), set(), set()
    public_inputs, canonical_inputs, role_sources, physical_runs = (
        set(),
        set(),
        set(),
        set(),
    )
    collectors = {}
    held_out_ids, held_out_inputs = set(), set()
    validated = []
    frequencies = collections.Counter()
    for member in members:
        fields(
            member,
            ("id", "profile", "eligible_case_ids"),
            "invalid usage profile member fields",
        )
        require(
            isinstance(member["id"], str)
            and member["id"]
            and member["id"] not in member_ids,
            "duplicate or invalid usage profile member ID",
        )
        member_ids.add(member["id"])
        child = source_json(root, member["profile"])
        checksum = member["profile"]["sha256"]
        require(checksum not in profile_hashes, "duplicate usage member profile")
        profile_hashes.add(checksum)
        # No recursion or relaxed v1 projection: validate every member's entire
        # cases/receipts/cohort/dispatch inventory through the original path.
        counts = profile_frequencies(root, child, member, binding)
        profile_data(root, child, directory)
        original_loop = referenced_json(
            root, child["compiled_cohort"]["data_manifests"]["loop"]
        )

        def noncache_files(loop):
            return {
                path: record
                for path, record in loop["files"].items()
                if path != "cache.json" and not path.startswith("cache/")
            }

        require(
            same(noncache_files(original_loop), noncache_files(manifest))
            and all(
                same(original_loop.get(name), manifest.get(name))
                for name in (
                    "masters",
                    "families",
                    "dimension",
                    "normalization",
                    "unit_mass_squared",
                )
            ),
            "active noncache data or terminal catalogue differs from original usage",
        )
        require(
            same(child["data"], common["data"]),
            "usage member data differs from common data",
        )
        require(
            all(
                same(child["compiled_cohort"].get(name), compiled[name])
                for name in COMMON_COHORT_FIELDS
            ),
            "usage member differs from common compiled source cohort",
        )
        collector = child["compiled_cohort"].get("collector", "measure_cache")
        executable = child["compiled_cohort"]["measurement_executable_sha256"]
        require(
            (collector not in collectors or collectors[collector] == executable)
            and all(
                name == collector or checksum != executable
                for name, checksum in collectors.items()
            ),
            "composed collectors must retain their distinct named executables",
        )
        collectors[collector] = executable
        documents, child_held_ids, child_held_inputs = embedded_eligibility(child)
        authority = documents.get(common["held_out_authority_sha256"], {})
        require(
            authority.get("schema") == "vakint.five-loop-frozen-public-suites.v1"
            and isinstance(authority.get("held_out"), list)
            and authority["held_out"]
            and all(
                isinstance(row, dict) and isinstance(row.get("public_input"), str)
                for row in authority["held_out"]
            ),
            "usage member lacks the common frozen held-out authority",
        )
        authority_ids = [row["id"] for row in authority["held_out"]]
        authority_inputs = [
            hashlib.sha256(row["public_input"].encode()).hexdigest()
            for row in authority["held_out"]
        ]
        require(
            len(set(authority_ids)) == len(authority_ids)
            and len(set(authority_inputs)) == len(authority_inputs),
            "common frozen held-out authority repeats an ID or input",
        )
        held_out_ids.update(child_held_ids)
        held_out_inputs.update(child_held_inputs)
        require(
            set(member["eligible_case_ids"])
            == {case["case_id"] for case in child["cases"]},
            "composed member must select exactly its actual cases",
        )
        for case in child["cases"]:
            if case["role"] == "tuning":
                tuning = authority.get("tuning", [])
                require(
                    isinstance(tuning, list), "invalid common frozen tuning inventory"
                )
                authorized = [
                    row
                    for row in tuning
                    if isinstance(row, dict) and row.get("id") == case["case_id"]
                ]
                require(
                    len(authorized) == 1
                    and isinstance(authorized[0].get("public_input"), str)
                    and hashlib.sha256(
                        authorized[0]["public_input"].encode()
                    ).hexdigest()
                    == case["public_input_source_sha256"],
                    "composed tuning case differs from the compiled frozen suite",
                )
            require(case["case_id"] not in case_ids, "duplicate composed usage case ID")
            case_ids.add(case["case_id"])
            require(
                case["receipt"]["sha256"] not in receipt_hashes,
                "reused composed usage case receipt",
            )
            receipt_hashes.add(case["receipt"]["sha256"])
            role = (
                case["role_evidence"]["document_sha256"],
                case["role_evidence"]["json_pointer"],
            )
            require(
                role not in role_sources
                and case["public_input_source_sha256"] not in public_inputs
                and case["input_sha256"] not in canonical_inputs,
                "composed usage repeats a case source or input",
            )
            role_sources.add(role)
            public_inputs.add(case["public_input_source_sha256"])
            canonical_inputs.add(case["input_sha256"])
            require(
                same(
                    case["cache_identity"],
                    {
                        "cache_sha256": None,
                        "cache_native_index_identity": index,
                    },
                ),
                "composed usage case is not on the common cumulative index",
            )
            composed_case_settings(
                root,
                child,
                case,
                common["raw_reduction_settings"],
                common["output_conventions"],
            )
            receipt = referenced_json(root, case["receipt"])
            if receipt.get("schema") == "vakint.physical-cache-usage-receipt.v1":
                for prefix in ("reference_", ""):
                    launch = referenced_json(root, receipt[prefix + "launch"])
                    run = (
                        child["compiled_cohort"]["measurement_executable_sha256"],
                        launch["collector"]["pid"],
                        launch["collector"]["start_ticks"],
                    )
                    require(
                        run not in physical_runs,
                        "composed usage reuses a physical collector process",
                    )
                    physical_runs.add(run)
        validated.append(child)
        for key, count in counts.items():
            frequencies[key] = checked_sum((frequencies[key], count))
    require(
        set(requested) == case_ids,
        "selected eligible cases differ from composed member union",
    )
    for child in validated:
        for case in child["cases"]:
            require(
                case["case_id"] not in held_out_ids
                and case["public_input_source_sha256"] not in held_out_inputs,
                "composed usage launders a held-out case or input",
            )
    return frequencies


def composed_case_settings(root, profile, case, common, conventions):
    """Compare actual resolved runtime settings, never an inferred source mode."""
    # The original manifest is immutable evidence even when publication changes
    # the current root/cache hashes. Native conventions must match the active
    # application and source binding, not a caller-supplied settings assertion.
    references = profile["compiled_cohort"]["data_manifests"]
    loop = referenced_json(root, references["loop"])
    fields(
        conventions,
        (
            "integral_normalization",
            "integral_normalization_expression",
            "epsilon_symbol",
        ),
        "invalid composed output conventions",
    )
    require(
        all(isinstance(value, str) and value for value in conventions.values()),
        "invalid composed output convention value",
    )
    fields(
        common,
        (
            "master_mode",
            "coefficient_representation",
            "dimension",
            "normalization",
            "unit_mass_squared",
        ),
        "invalid composed raw reduction settings",
    )
    require(
        common["master_mode"] == "retain"
        and common["coefficient_representation"] == "sparse"
        and common["dimension"] == loop.get("dimension")
        and common["normalization"] == loop.get("normalization")
        and common["unit_mass_squared"] is True
        and loop.get("unit_mass_squared") is True,
        "composed raw settings differ from authenticated native conventions",
    )
    receipt = referenced_json(root, case["receipt"])
    if profile["compiled_cohort"].get("collector", "measure_cache") == "measure_cache":
        require(
            same(receipt.get("raw_reduction_settings"), common),
            "tuning receipt lacks matching actual resolved raw settings",
        )
        require(
            same(
                receipt.get("raw_reduction_settings_source"),
                {
                    "data_version": loop["version"],
                    "release_manifest_sha256": profile["data"]["root_manifest_sha256"],
                    "loop_manifest_sha256": profile["data"]["loop_manifest_sha256"],
                    "loop_count": 5,
                },
            ),
            "tuning resolved settings have different original data authority",
        )
        actual_reports = [receipt]
        require(
            same(receipt.get("cache_identity_after"), case["cache_identity"]),
            "tuning source index changed during evaluation",
        )
        require(
            receipt.get("persistent_cache_policy") == "manual-five-loop-only"
            and receipt.get("running_cache") is None
            and same(
                receipt.get("persistent_cache_attachments_before"),
                {str(i): False for i in range(1, 6)},
            )
            and same(
                receipt.get("persistent_cache_attachments_during_evaluation"),
                {str(i): i == 5 for i in range(1, 6)},
            ),
            "composed tuning usage requires a read-only five-loop backing",
        )
    else:
        actual_reports = []
        for prefix in ("reference_", ""):
            report = referenced_json(root, receipt[prefix + "benchmark"])
            require(
                report.get("master_mode") == common["master_mode"]
                and report.get("coefficient_representation")
                == common["coefficient_representation"],
                "physical report differs from composed resolved raw settings",
            )
            actual_reports.append(report)
    for report in actual_reports:
        actual = report.get("conventions", {})
        require(
            isinstance(actual, dict)
            and all(
                same(actual.get(name), value) for name, value in conventions.items()
            ),
            "actual output conventions differ across composed usage",
        )


def admitted_profile_frequencies(
    root, profile, selected, binding, directory, source, manifest
):
    if isinstance(profile, dict) and profile.get("schema") == PROFILE_V2_SCHEMA:
        return composed_profile_frequencies(
            root, profile, selected, binding, directory, source, manifest
        )
    frequencies = profile_frequencies(root, profile, selected, binding)
    profile_data(root, profile, directory)
    require(
        profile["data"]["application_sha256"]
        == data.digest(directory / "ibps/application.json"),
        "usage application differs from selected cache",
    )
    return frequencies


def selection_source(root, source):
    """Authenticate the existing cumulative source without opening Native data."""
    fields(
        source,
        (
            "producer",
            "data_manifest_sha256",
            "cache_native_index_identity",
            "inventory",
        ),
        "invalid cumulative source provenance",
    )
    require(
        hash256(source["data_manifest_sha256"]),
        "invalid cumulative source data identity",
    )
    native_index_identity(source["cache_native_index_identity"])
    producer = source_json(root, source["producer"])
    require(isinstance(producer, dict), "cumulative producer must be an object")
    binding = producer.get("semantic_binding")
    semantic_binding(binding)
    require(
        isinstance(producer, dict)
        and producer.get("schema") == "vakint.cumulative-native-cache-report.v1"
        and producer.get("cache_sha256") is None
        and same(
            producer.get("cache_native_index_identity"),
            source["cache_native_index_identity"],
        )
        and producer.get("data_manifest_sha256") == source["data_manifest_sha256"]
        and isinstance(producer.get("sources"), list)
        and producer["sources"],
        "selected cache source is not the authenticated cumulative producer",
    )
    source_file(root, source["inventory"])
    return binding


def work_document(key):
    result = {"kind": key[0], "powers": list(key[1])}
    if key[0] == "apply":
        result["owner_sector"] = list(key[2])
    return result


def rank_observed_work(physical, tuning, arity, frequencies):
    """Rank validated observations; counts are neither work nor byte estimates."""
    cases, dispatches, recomputed = {}, collections.Counter(), collections.Counter()
    core = set()
    for child in (physical, tuning):
        case = child["cases"][0]
        for dispatch in case["dispatches"]:
            roots = {work(row, arity) for row in dispatch["collected_roots"]}
            for row in dispatch["records"]:
                key = work(row["work"], arity)
                count = row["backing_hits"]
                if count:
                    cases.setdefault(key, set()).add(case["case_id"])
                    dispatches[key] += 1
                    recomputed[key] = checked_sum((recomputed[key], count))
                    if child is physical and key[0] == "route" and key in roots:
                        core.add(key)
    require(
        recomputed == frequencies, "ranked observations differ from validated usage"
    )
    require(core, "physical usage has no positively hit requested Route CORE")
    extras = sorted(
        set(frequencies) - core,
        key=lambda key: (-len(cases[key]), -dispatches[key], -frequencies[key], key),
    )
    return core, extras, cases, dispatches


def author_candidates(
    root,
    directory,
    manifest,
    source,
    physical_ref,
    tuning_ref,
    additions,
    output_relative,
    physical_route_limit=None,
):
    """Author existing profile/key formats from accepted observations only.

    No Native payloads, reductions or byte-cost estimates are involved. Actual
    selected exports decide the compressed and decoded budgets independently.
    """
    root, directory = Path(root), Path(directory)
    require(
        root.is_absolute() and root.is_dir() and not root.is_symlink(),
        "invalid authoring proof root",
    )
    require(
        isinstance(output_relative, str) and output_relative.startswith("provenance/"),
        "authoring output must be a new root-relative provenance directory",
    )
    output = data.checked_path(root, output_relative)
    require(not output.exists(), "authoring output already exists")
    for path in (output, *output.parents):
        if path == root.parent:
            break
        require(not path.is_symlink(), "symlink in authoring output path")
    require(
        isinstance(additions, list)
        and additions
        and all(value == "all" or integer(value, 0, U64_MAX) for value in additions)
        and len(set(additions)) == len(additions),
        "additional-key counts must be unique nonnegative integers or all",
    )
    require(
        physical_route_limit is None or integer(physical_route_limit, 1, U64_MAX),
        "physical-route limit must be a positive integer",
    )
    binding = selection_source(root, source)
    if isinstance(manifest.get("cache"), dict):
        require(
            same(binding, manifest["cache"].get("binding")),
            "active cache binding differs from selected source",
        )
    physical = source_json(root, physical_ref)
    tuning = source_json(root, tuning_ref)
    for profile, collector, role in (
        (physical, "five_loop_qcd_ladder", "physical-example"),
        (tuning, "measure_cache", "tuning"),
    ):
        require(
            isinstance(profile, dict)
            and profile.get("schema") == "vakint.cache-record-usage-profile.v1"
            and isinstance(profile.get("compiled_cohort"), dict)
            and profile["compiled_cohort"].get("collector", "measure_cache")
            == collector
            and isinstance(profile.get("cases"), list)
            and len(profile["cases"]) == 1
            and isinstance(profile["cases"][0], dict)
            and profile["cases"][0].get("role") == role,
            "authoring requires one physical case and one frozen tuning case",
        )
    compiled = physical["compiled_cohort"]
    require(
        all(name in compiled for name in COMMON_COHORT_FIELDS),
        "physical profile lacks its complete compiled source cohort",
    )
    snapshot = referenced_json(root, compiled["main_source_snapshot"])
    authority = (
        snapshot.get("files", {})
        .get("crates/vakint/examples/build_cache/frozen-public-suites.json", {})
        .get("sha256")
    )
    require(
        hash256(authority), "physical source lacks its compiled frozen-suite authority"
    )
    tuning_receipt = referenced_json(root, tuning["cases"][0]["receipt"])
    conventions = tuning_receipt.get("conventions", {})
    profile = {
        "schema": PROFILE_V2_SCHEMA,
        "semantic_binding": binding,
        "common": {
            "source_cache_native_index_identity": source["cache_native_index_identity"],
            "data": physical["data"],
            "compiled_source_cohort": {
                name: compiled[name] for name in COMMON_COHORT_FIELDS
            },
            "raw_reduction_settings": tuning_receipt.get("raw_reduction_settings"),
            "output_conventions": {
                name: conventions.get(name)
                for name in (
                    "integral_normalization",
                    "integral_normalization_expression",
                    "epsilon_symbol",
                )
            },
            "held_out_authority_sha256": authority,
        },
        "members": [
            {
                "id": name,
                "profile": reference,
                "eligible_case_ids": [child["cases"][0]["case_id"]],
            }
            for name, reference, child in (
                ("physical", physical_ref, physical),
                ("tuning", tuning_ref, tuning),
            )
        ],
    }
    eligible = sorted(child["cases"][0]["case_id"] for child in (physical, tuning))
    frequencies = admitted_profile_frequencies(
        root,
        profile,
        {"eligible_case_ids": eligible},
        binding,
        directory,
        source,
        manifest,
    )
    core, extras, cases, dispatches = rank_observed_work(
        physical, tuning, binding["physical_arity"], frequencies
    )
    require(
        physical_route_limit is None or physical_route_limit <= len(core),
        "physical-route limit exceeds observed physical CORE",
    )
    ranked_core = sorted(
        core,
        key=lambda key: (-len(cases[key]), -dispatches[key], -frequencies[key], key),
    )
    selected_core = set(ranked_core[:physical_route_limit])
    counts = sorted(
        {0, *(len(extras) if value == "all" else value for value in additions)}
    )
    require(
        all(count <= len(extras) for count in counts),
        "additional-key count exceeds eligible keys",
    )

    def json_bytes(value):
        raw = (
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        ).encode()
        require(
            len(raw) < GIT_FILE_BYTES_LIMIT,
            "authoring proof exceeds decoded file limit",
        )
        return raw

    def encoded(value):
        raw = gzip.compress(json_bytes(value), mtime=0)
        require(
            len(raw) < GIT_FILE_BYTES_LIMIT,
            "authoring proof exceeds encoded file limit",
        )
        return raw

    def reference(name, raw):
        return {
            "path": f"{output_relative}/{name}",
            "sha256": hashlib.sha256(raw).hexdigest(),
        }

    profile_bytes = encoded(profile)
    profile_ref = reference("usage-profile.json.gz", profile_bytes)
    ranking = {
        "schema": "vakint.cache-record-selection-ranking.v1",
        "usage_profile_sha256": profile_ref["sha256"],
        "method": "physical-requested-route-core-then-case-dispatch-hit-frequency",
        "per_key_native_work_avoided": None,
        "per_key_compressed_bytes": None,
        "cost_policy": "Actual Native exports determine nonadditive compressed/decoded cost.",
        "rows": [
            {
                "work": work_document(key),
                "core": key in core,
                "eligible_case_ids": sorted(cases[key]),
                "dispatch_occurrences": dispatches[key],
                "backing_hits": frequencies[key],
            }
            for key in (*sorted(core), *extras)
        ],
    }
    ranking_bytes = encoded(ranking)
    ranking_ref = reference("ranking.json.gz", ranking_bytes)
    files = {"usage-profile.json.gz": profile_bytes, "ranking.json.gz": ranking_bytes}
    candidates = []
    for count in counts:
        keys = sorted(selected_core | set(extras[:count]))
        document = {
            "schema": "vakint.cache-record-selection.v1",
            "semantic_binding": binding,
            "usage_profile_sha256": profile_ref["sha256"],
            "eligible_case_ids": eligible,
            "keys": [work_document(key) for key in keys],
            "selection": {
                "method": ranking["method"],
                "max_compressed_bytes": data.FIVE_LOOP_LIGHT_CACHE_BYTES_LIMIT,
                "core_keys": len(selected_core),
                "additional_keys": count,
                "ranking_sha256": ranking_ref["sha256"],
            },
        }
        name = f"selected-keys-{count:06d}.json.gz"
        files[name] = encoded(document)
        candidates.append(
            {
                "keys": reference(name, files[name]),
                "core_keys": len(selected_core),
                "total_core_keys": len(core),
                "selected_core_keys": len(selected_core),
                "additional_keys": count,
                "unique_keys": len(keys),
                "compressed_cache_bytes": None,
                "decoded_cache_bytes": None,
                "native_export_accepted": False,
            }
        )
    report = {
        "schema": "vakint.light-cache-selection-authoring.v1",
        "status": "VALIDATED_USAGE_METADATA_ONLY_NATIVE_EXPORT_PENDING",
        "source": source,
        "semantic_binding": binding,
        "usage_profile": profile_ref,
        "ranking": ranking_ref,
        "eligible_case_ids": eligible,
        "core_keys": len(selected_core),
        "total_core_keys": len(core),
        "selected_core_keys": len(selected_core),
        "eligible_unique_keys": len(frequencies),
        "candidates": candidates,
        "final_held_out_used": False,
        "coverage_claim": False,
        "native_payloads_opened": False,
        "native_reduction_performed": False,
    }
    files["authoring-report.json"] = json_bytes(report)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".light-authoring-", dir=output.parent))
    reserved = None
    try:
        for name, raw in files.items():
            (staging / name).write_bytes(raw)
        # Reserve with exclusive mkdir: rename must not replace another
        # concurrently created empty directory between exists() and rename().
        output.mkdir()
        reserved = output.stat()
        os.rename(staging, output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
            if reserved is not None and output.exists():
                current = output.stat()
                if (current.st_dev, current.st_ino) == (
                    reserved.st_dev,
                    reserved.st_ino,
                ):
                    output.rmdir()
    return report


def validate(directory, manifest, metadata):
    """Return a recomputed admission record, never a new Native algebra claim."""
    require(
        same(
            decode_json((directory / manifest["cache"]["metadata"]).read_bytes()),
            metadata,
        ),
        "usage metadata differs from its strict JSON payload",
    )
    fields(
        metadata,
        ("schema", "strict", "coverage_claim", "selection"),
        "usage-selected metadata must not claim finite workload completion",
    )
    require(
        metadata["strict"] is True and metadata["coverage_claim"] is False,
        "usage selection must remain strict without a coverage claim",
    )
    selection = metadata["selection"]
    fields(
        selection,
        (
            "kind",
            "source",
            "keys",
            "unique_keys",
            "usage_profile",
            "allowed_input_classes",
            "final_held_out_used",
            "validation",
        ),
        "invalid usage-selected provenance fields",
    )
    require(
        selection["kind"] == "usage-selected-strict-snapshot"
        and selection["allowed_input_classes"] == ["tuning", "physical-example"]
        and selection["final_held_out_used"] is False
        and integer(selection["unique_keys"], 1, U64_MAX),
        "usage selection includes unsupported or final held-out inputs",
    )
    root = directory.parent
    source = selection["source"]
    binding = selection_source(root, source)
    require(
        same(binding, manifest["cache"]["binding"]),
        "selected cache source binding differs from manifest",
    )
    profile = source_json(root, selection["usage_profile"])
    keys = source_json(root, selection["keys"])
    fields(
        keys,
        (
            "schema",
            "semantic_binding",
            "usage_profile_sha256",
            "eligible_case_ids",
            "keys",
            "selection",
        ),
        "invalid selected-key document",
    )
    require(
        keys["schema"] == "vakint.cache-record-selection.v1"
        and same(keys["semantic_binding"], binding)
        and keys["usage_profile_sha256"] == selection["usage_profile"]["sha256"]
        and isinstance(keys["selection"], dict)
        and isinstance(keys["selection"].get("method"), str)
        and keys["selection"]["method"].strip()
        and type(keys["selection"].get("max_compressed_bytes")) is int
        and keys["selection"]["max_compressed_bytes"]
        == data.FIVE_LOOP_LIGHT_CACHE_BYTES_LIMIT,
        "selected keys differ from eligible profile, binding or compressed budget",
    )
    frequencies = admitted_profile_frequencies(
        root, profile, keys, binding, directory, source, manifest
    )
    require(isinstance(keys["keys"], list) and keys["keys"], "empty selected key list")
    selected = [work(row, binding["physical_arity"]) for row in keys["keys"]]
    require(
        len(set(selected)) == len(selected) == selection["unique_keys"]
        and all(frequencies[key] > 0 for key in selected),
        "selected keys are duplicated or lack positive eligible frequency",
    )
    raw = source_json(root, selection["validation"])
    require(isinstance(raw, dict), "Native validation receipt must be an object")
    if profile.get("schema") == PROFILE_V2_SCHEMA:
        require(
            raw.get("usage_profile_schema_sha256") == PROFILE_V2_SCHEMA_SHA256,
            "Native exporter must stamp the actual composed usage schema",
        )
    cohort_ids(raw.get("compiled_cohort"))
    identity = manifest["cache"]["identity"]
    cache_sha256 = data.digest(directory / manifest["cache"]["path"])
    require(
        raw.get("schema") == "vakint.strict-light-cache-native-validation.v1"
        and raw.get("success") is True
        and same(raw.get("semantic_binding"), binding)
        and same(
            raw.get("source_cache_native_index_identity"),
            source["cache_native_index_identity"],
        )
        and raw.get("cache_sha256") == cache_sha256
        and same(raw.get("cache_identity"), identity)
        and raw.get("decoded_sha256") == manifest["cache"]["decoded_sha256"]
        and raw.get("selected_keys_sha256") == selection["keys"]["sha256"]
        and raw.get("source_inventory_sha256") == source["inventory"]["sha256"]
        and raw.get("usage_profile_sha256") == selection["usage_profile"]["sha256"],
        "strict Native validation differs from selected cache/source/proofs",
    )
    for name in ("selected_records", "reimported_records", "complete_records"):
        require(
            type(raw.get(name)) is int and raw[name] == len(selected),
            "strict Native selected/reimported/complete counts differ",
        )
    require(
        all(
            type(raw.get(name)) is int and raw[name] == 0
            for name in ("missing_keys", "partial_records")
        )
        and all(
            raw.get(name) is True
            for name in (
                "exact_record_and_ordered_guard_equality",
                "declared_terminal_validation",
                "source_unchanged",
            )
        )
        and type(raw.get("codec_state_format")) is int
        and raw["codec_state_format"] == 6
        and isinstance(raw.get("compiled_cohort"), dict)
        and raw["compiled_cohort"]
        and isinstance(raw.get("collector_artifacts"), dict)
        and hash256(raw["collector_artifacts"].get("sha256"))
        and hash256(raw.get("executable_sha256")),
        "strict Native validation is incomplete or not source-bound",
    )
    native_artifact(root, raw)
    require(
        not any(
            name in raw
            for name in (
                "metadata",
                "cache_metadata",
                "metadata_sha256",
                "cache_metadata_sha256",
                "selection_admission",
                "output",
            )
        ),
        "Native validation must not create a cache metadata hash cycle",
    )
    require(
        integer(
            identity["compressed_bytes"], 1, data.FIVE_LOOP_LIGHT_CACHE_BYTES_LIMIT
        ),
        "usage-selected LIGHT cache exceeds compressed publication budget",
    )
    return {
        "schema": "vakint.light-cache-selection-admission.v1",
        "accepted": True,
        "cache_metadata_sha256": data.digest(directory / manifest["cache"]["metadata"]),
        "selected_keys_sha256": selection["keys"]["sha256"],
        "usage_profile_sha256": selection["usage_profile"]["sha256"],
        "source_inventory_sha256": source["inventory"]["sha256"],
        "native_validation_sha256": selection["validation"]["sha256"],
        "semantic_binding": binding,
        "source_cache_native_index_identity": source["cache_native_index_identity"],
        "selected_unique_keys": len(selected),
        "eligible_profile_unique_keys": len(frequencies),
        "checks": {
            name: True
            for name in (
                "authenticated_eligible_sources",
                "dispatch_counts_reconciled",
                "positive_frequency_selected_subset",
                "final_held_out_excluded",
            )
        },
        "scope": "Portable source eligibility and frequency admission; actual Native validation remains its separately authenticated receipt. Raw traces remain hash-bound audit material, not replayed here.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    author = commands.add_parser(
        "author",
        help="Compose accepted observations and freeze candidate keys; no Native work",
    )
    author.add_argument(
        "--root",
        type=Path,
        required=True,
        help="Absolute provenance/data root containing all authenticated references",
    )
    for name in ("loop-manifest", "source", "physical-profile", "tuning-profile"):
        author.add_argument(
            f"--{name}", required=True, help="Safe path relative to --root"
        )
        author.add_argument(f"--{name}-sha256", required=True)
    author.add_argument(
        "--additional-keys",
        action="append",
        default=None,
        help="Cumulative extra-key count, or all; repeat to freeze a schedule. Selected physical CORE is always included.",
    )
    author.add_argument(
        "--physical-route-limit",
        type=int,
        default=None,
        help="Positive count of physical CORE routes ranked by observed case/dispatch/hit frequency; default includes all",
    )
    author.add_argument(
        "--output-dir",
        required=True,
        help="NEW root-relative provenance directory; never overwritten",
    )
    args = parser.parse_args(argv)
    try:

        def reference(name):
            return {
                "path": getattr(args, name),
                "sha256": getattr(args, name + "_sha256"),
            }

        # The active manifest lives in 5L/, unlike immutable proof references.
        # Do not relax source_file's provenance-only policy to read it.
        manifest_path = data.checked_path(args.root, args.loop_manifest)
        current = args.root
        for part in PurePosixPath(args.loop_manifest).parts:
            current /= part
            require(not current.is_symlink(), "loop manifest path contains a symlink")
        require(
            hash256(args.loop_manifest_sha256)
            and manifest_path.is_file()
            and manifest_path.stat().st_size < GIT_FILE_BYTES_LIMIT
            and data.digest(manifest_path) == args.loop_manifest_sha256,
            "active loop manifest SHA256 or file differs",
        )
        manifest = decode_json(manifest_path.read_bytes())
        source = source_json(args.root, reference("source"))
        additions = [
            value if value == "all" else int(value)
            for value in (args.additional_keys or ["0"])
        ]
        report = author_candidates(
            args.root,
            data.checked_path(args.root, args.loop_manifest).parent,
            manifest,
            source,
            reference("physical_profile"),
            reference("tuning_profile"),
            additions,
            args.output_dir,
            physical_route_limit=args.physical_route_limit,
        )
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as error:
        parser.exit(2, f"cache usage authoring failed: {error}\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
