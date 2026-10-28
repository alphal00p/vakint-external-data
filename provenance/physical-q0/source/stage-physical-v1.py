"""Stage this actual q0 OFF/ON pair and call the unchanged portable v1 owner.

Metadata only: no Symbolica, Native cache, integral catalogue, reduction,
numerical evaluator, candidate author or cache exporter is imported or invoked.
"""
from pathlib import Path, PurePosixPath
from collections import Counter
import argparse
import base64
import ctypes
import hashlib
import importlib
import json
import os
import shutil
import sys

LIMIT = 100 * 1024 * 1024
OWNER_SOURCE_SHA256 = {
    "cache_usage.py": "4c1b9c905962739edc5bbb27443838c144489a73a625ad865e3e5fec95f8f8db",
    "data.py": "b07bab2f8021c2ddd97c6c3f9776c3e7ef9fca54d3c386a59c448601c3808627",
    "saved_cache.py": "fb09a576ca8126a383cacad62e8dac5420240c42986819fde84e8a301c2feec6",
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def unique_json(raw):
    def pairs(rows):
        out = {}
        for key, value in rows:
            require(key not in out, "duplicate JSON key")
            out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def checked(row):
    path = Path(row["path"])
    require(path.is_absolute() and path.is_file() and not path.is_symlink(), "regular absolute input required")
    require(path.stat().st_size < LIMIT, "metadata input exceeds repository file limit")
    require(digest(path) == row["sha256"], "input checksum changed: " + str(path))
    if "bytes" in row:
        require(type(row["bytes"]) is int and path.stat().st_size == row["bytes"], "input length changed")
    return path


def load(row):
    return unique_json(checked(row).read_bytes())


def safe_relative(text):
    require(isinstance(text, str) and all(x not in ("", ".", "..") for x in text.split("/")), "unsafe archive spelling")
    path = PurePosixPath(text)
    require(not path.is_absolute() and path.parts and all(x not in (".", "..") for x in path.parts), "unsafe archive path")
    return Path(*path.parts)


def copy_input(root, row, relative):
    source = checked(row)
    relative_path = safe_relative(relative)
    require(root.is_dir() and not root.is_symlink(), "archive root must be a real directory")
    parent = root
    for part in relative_path.parts[:-1]:
        parent = parent / part
        require(not parent.is_symlink(), "archive parent is a symlink")
        parent.mkdir(exist_ok=True)
        require(parent.is_dir(), "archive parent is not a directory")
    target = parent / relative_path.name
    require(not target.exists() and not target.is_symlink(), "archive target already exists")
    with source.open("rb") as source_stream, target.open("xb") as target_stream:
        shutil.copyfileobj(source_stream, target_stream)
        target_stream.flush()
        os.fsync(target_stream.fileno())
    require(digest(target) == row["sha256"], "archive copy changed")
    return {"path_hint": relative, "sha256": row["sha256"]}


def write_json(path, document):
    require(not path.exists(), "output already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(document, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def publish_new_directory(source, target):
    libc = ctypes.CDLL(None, use_errno=True)
    rename = libc.renameat2
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(source), -100, os.fsencode(target), 1) != 0:
        raise OSError(ctypes.get_errno(), "atomic metadata destination must be new")


def observed_work(value, arity):
    require(isinstance(value, dict) and set(value) == {"stage", "powers", "owner_sector"}, "malformed Native trace work")
    powers = value["powers"]
    require(isinstance(powers, list) and len(powers) == arity
            and all(type(x) is int and -(1 << 63) <= x < (1 << 63) for x in powers), "invalid observed powers")
    stage = value["stage"]
    require(stage in ("route", "apply"), "unknown observed stage")
    result = {"kind": stage, "powers": powers}
    if stage == "route":
        require(value["owner_sector"] is None, "Route work has an Apply owner")
    else:
        require(value["owner_sector"] == [x > 0 for x in powers]
                and all(type(x) is bool for x in value["owner_sector"]), "Apply owner differs from observed support")
        result["owner_sector"] = value["owner_sector"]
    return result


def dispatch_from_trace(trace, binding, accepted_persistent):
    """Project observed identities only; do not infer a recursive frontier."""
    require(trace.get("schema") == "vakint.cache-hit-diagnostic.v1"
            and trace.get("success") is True and trace.get("error") is None
            and trace.get("diagnostic_only") is True and type(trace.get("interval_ns")) is int
            and trace["interval_ns"] == 0 and trace.get("input_dispatch_count") == 1,
            "incomplete or sampled actual physical trace")
    events = trace.get("events")
    require(isinstance(events, list) and events, "missing actual hit events")
    roots, records = {}, Counter()
    active, finished, observer_finished, previous = False, False, False, -1
    final = None
    for event in events:
        kind = event.get("event")
        require(event.get("schema") == "vakint.cache-hit-events.v1", "trace event schema changed")
        if kind == "observer_finish":
            require(event is events[-1] and finished and not observer_finished
                    and event.get("observer_status") == "Active"
                    and event.get("operation_succeeded") is True and event.get("interval_ns") == 0,
                    "observer did not finish completely")
            observer_finished = True
            continue
        sequence = event.get("sequence")
        require(type(sequence) is int and sequence > previous, "non-increasing actual event sequence")
        previous = sequence
        require(event.get("family_fingerprint") == binding["family_fingerprint"], "trace belongs to another Native family")
        if kind == "dispatch_start":
            require(not active and not finished, "extra or overlapping physical dispatch")
            active = True
        elif kind == "backing_hit":
            require(active and not finished, "hit outside active dispatch")
            work = observed_work(event["work"], binding["physical_arity"])
            records[json.dumps(work, sort_keys=True, separators=(",", ":"))] += 1
        elif kind == "root_collected":
            require(active and not finished, "root outside active dispatch")
            work = observed_work(event["rootwork"], binding["physical_arity"])
            require(work["kind"] == "route", "collected physical root is not Route work")
            key = json.dumps(work, sort_keys=True, separators=(",", ":"))
            require(key not in roots, "duplicate collected physical root")
            roots[key] = work
            require(event.get("completed_roots") == len(roots), "collected-root counter gap")
        elif kind == "dispatch_finish":
            require(active and not finished and event.get("status") == "succeeded", "unsuccessful dispatch finish")
            require(event.get("requested_roots") == event.get("completed_roots") == len(roots), "incomplete physical roots")
            final = event
            active, finished = False, True
        else:
            raise ValueError("unknown actual trace event: " + str(kind))
    require(finished and observer_finished and final is not None, "missing terminal trace boundary")
    persistent = final["persistent"]
    names = ("lookups", "misses", "route_hits", "apply_hits", "requested_root_hits", "intermediate_hits")
    require(set(persistent) == set(names) and all(type(persistent[x]) is int
            and persistent[x] == accepted_persistent[x] for x in names), "trace/report counter mismatch")
    # This particular recorded pair has only observed requested Route hits.
    # Keep stronger proper-descendant/frontier claims explicitly unavailable.
    require(persistent["misses"] == persistent["apply_hits"] == persistent["intermediate_hits"] == 0
            and persistent["route_hits"] == persistent["requested_root_hits"] == len(roots)
            and set(records) == set(roots) and all(n == 1 for n in records.values()),
            "actual q0 trace is not the recorded requested-Route-only workload")
    return {"ordinal": 0, "requested_roots": final["requested_roots"],
            "completed_roots": final["completed_roots"],
            "collected_roots": [roots[k] for k in sorted(roots)], "persistent": persistent,
            "records": [{"work": json.loads(k), "backing_hits": records[k]} for k in sorted(records)]}


def check_owner_sources(tools, rows):
    tools = Path(tools)
    require(tools.is_absolute() and tools.resolve() == tools, "canonical tools path must be absolute and resolved")
    require(set(rows) == set(OWNER_SOURCE_SHA256), "incomplete canonical owner dependency sources")
    for name, row in rows.items():
        require(row["sha256"] == OWNER_SOURCE_SHA256[name]
                and checked(row) == tools / name, "canonical owner source path/hash changed")
    return tools


def stage(request_path, request_sha):
    require(digest(request_path) == request_sha, "request changed")
    request = unique_json(Path(request_path).read_bytes())
    require(request["schema"] == "vakint.actual-q0-physical-v1-stage-request.v1", "wrong fixed staging request")
    output = Path(request["output"])
    require(output.is_absolute() and not output.exists(), "fresh absolute output required")
    pending = output.with_name(output.name + ".pending")
    require(not pending.exists(), "staging destination already exists")
    for source in request["protected_roots"]:
        source = Path(source).resolve()
        require(not output.resolve().is_relative_to(source)
                and not source.is_relative_to(output.resolve()), "output overlaps immutable source")
    tools = check_owner_sources(request["owner_tools"], request["owner_sources"])
    pending.mkdir()
    root = pending / "root"
    root.mkdir()
    try:
        producer_path = Path(__file__).resolve()
        producer_source = copy_input(root, {"path": str(producer_path), "sha256": digest(producer_path)},
                                     "provenance/physical-q0/source/stage-physical-v1.py")
        request_source = copy_input(root, {"path": str(Path(request_path).resolve()), "sha256": request_sha},
                                    "provenance/physical-q0/source/request.json")
        owner_archives = {name: copy_input(root, row, "provenance/physical-q0/canonical-owner/" + name)
                          for name, row in request["owner_sources"].items()}
        for row in request["cohort_archive"]:
            copy_input(root, row, "provenance/actual-two-collector-cohort/" + row["relative"])
        data_refs = {}
        for name, row in request["data"].items():
            data_refs[name] = copy_input(root, row, "provenance/physical-q0/data/" + name + ".json")
        for name, relative in (("root", "manifest.json"), ("loop", "5L/manifest.json"),
                               ("application", "5L/ibps/application.json"),
                               ("prepared", "5L/benchmarks/zero-momentum/prepared-input.json")):
            copy_input(root, request["data"][name], relative)
        all5 = load(request["all5_source"])
        require(all5["cache_native_index_identity"] == request["cache_identity"]["cache_native_index_identity"]
                and all5["semantic_binding"] == request["semantic_binding"]
                and all5["data_manifest_sha256"] == request["data"]["root"]["sha256"],
                "actual cumulative all5 source differs")
        copy_input(root, request["all5_source"], "provenance/physical-q0/all5-cumulative-report.json")
        pair_refs, reports = {}, {}
        for role in ("off", "on"):
            inputs = request[role]
            report = load(inputs["benchmark"])
            reports[role] = report
            for name, row in inputs.items():
                pair_refs[(role, name)] = copy_input(root, row, f"provenance/physical-q0/{role}/{name}.json")
        on, off = reports["on"], reports["off"]
        for role, inputs in (("off", request["off"]), ("on", request["on"])):
            proof, science = load(inputs["verification"]), load(inputs["science"])
            completion = load(inputs["completion"])
            require(proof["status"] == "PASS" and proof["full_scalar_coefficient_count"] == 58
                    and proof["master_identity_union_count"] == 55 and proof["guard_count"] == 146678
                    and proof["Float_numeric_atoms_rejected"] is True
                    and science["actual_source"] == request["Main_revision"]
                    and completion["functional_acceptance"] is True
                    and completion["performance_eligible"] is False, "missing actual full scientific/supervision proof")
            report = reports[role]
            require(science["verification"]["sha256"] == inputs["verification"]["sha256"]
                    and science["full58_proof"]["sha256"] == inputs["full58proof"]["sha256"]
                    and proof["full58_proof"]["sha256"] == inputs["full58proof"]["sha256"]
                    and science["execution"]["sha256"] == completion["raw_origins"]["raw-execution.json"]["sha256"]
                    and completion["functional_acceptance_authority"]["sha256"] == inputs["verification"]["sha256"]
                    and completion["raw_origins"]["raw-verification.json"]["sha256"] == inputs["verification"]["sha256"]
                    and completion["raw_origins"]["raw-full58-proof.json"]["sha256"] == inputs["full58proof"]["sha256"]
                    and completion["outputs"]["benchmark_sha256"] == inputs["benchmark"]["sha256"]
                    and completion["outputs"]["result_sha256"] == proof["whole_canonical_result_sha256"] == report["result_sha256"]
                    and completion["outputs"]["guards_sha256"] == report["guards"]["sha256"]
                    and completion["outputs"]["guards_count"] == report["guards"]["count"] == proof["guard_count"]
                    and proof["whole_ordered_guard_Atoms_equal"] is True
                    and proof["families_equal"] is True
                    and proof["whole_canonical_input_sha256"] == report["input_canonical_sha256"]
                    and proof["collector_source_head"] == request["Main_revision"]
                    and proof["cache_identity"] == science["cache_identity" if role == "off" else "exact_expected_all5_identity"] == request["cache_identity"]
                    and proof["measured_public_reduction_seconds"] == report["reduction_seconds"]
                    and all(proof["normalization"][key] == report["conventions"][key] for key in
                            ("integral_normalization", "integral_normalization_expression", "epsilon_symbol")),
                    "scientific evidence is crosswired to a different role/result/guards/convention")
        binding = on["saved_application_cache"]["binding"]
        require(binding == request["semantic_binding"], "different current semantic binding")
        for report in reports.values():
            require(report["cache_identity"] == report["cache_identity_after"] == request["cache_identity"]
                    and report["result_sha256"] == on["result_sha256"]
                    and report["guards"]["sha256"] == on["guards"]["sha256"], "OFF/ON or exact all5 identity differs")
        trace_ref = copy_input(root, request["trace"], "provenance/physical-q0/on/cache-hit-events.json")
        trace = load(request["trace"])
        require(on["cache_hit_diagnostic"]["sha256"] == trace_ref["sha256"]
                and on["cache_hit_diagnostic"]["classification_available"] is False,
                "trace/report differs or stronger classification was silently promoted")
        dispatch = dispatch_from_trace(trace, binding, on["saved_application_cache"]["persistent"])
        receipt = {"schema": "vakint.physical-cache-usage-receipt.v1"}
        for role, prefix in (("on", ""), ("off", "reference_")):
            for name in ("benchmark", "completion", "launch"):
                receipt[prefix + name] = pair_refs[(role, name)]
        receipt_path = root / "provenance/physical-q0/pair-receipt.json"
        write_json(receipt_path, receipt)
        documents = []
        for row in (request["physical_inventory"], request["frozen_heldouts"]):
            payload = checked(row).read_bytes()
            documents.append({"sha256": row["sha256"], "json_bytes_base64": base64.b64encode(payload).decode()})
        cohort = load(request["physical_cohort"])
        require(cohort["main_revision"] == request["Main_revision"]
                and cohort["measurement_executable_sha256"] == on["executable_sha256"], "wrong actual physical cohort")
        snapshot = unique_json((root / safe_relative(cohort["main_source_snapshot"]["path_hint"])).read_bytes())
        frozen = load(request["frozen_heldouts"])
        require(snapshot["files"]["crates/vakint/examples/build_cache/frozen-public-suites.json"]["sha256"]
                == request["frozen_heldouts"]["sha256"]
                and isinstance(frozen.get("held_out"), list) and len(frozen["held_out"]) == 12
                and len({row["id"] for row in frozen["held_out"]}) == 12,
                "complete compiled twelve-heldout authority differs")
        cohort["data_manifests"] = {name: data_refs[name] for name in ("root", "loop", "application")}
        profile = {"schema": "vakint.cache-record-usage-profile.v1", "semantic_binding": binding,
            "compiled_cohort": cohort,
            "data": {"root_manifest_sha256": request["data"]["root"]["sha256"],
                     "loop_manifest_sha256": request["data"]["loop"]["sha256"],
                     "application_sha256": request["data"]["application"]["sha256"]},
            "eligibility_documents": documents, "cases": [{"case_id": "q0", "role": "physical-example",
                "input_sha256": on["input_canonical_sha256"], "public_input_source_sha256": on["input_canonical_sha256"],
                "role_evidence": {"document_sha256": request["physical_inventory"]["sha256"], "json_pointer": "/cases/0"},
                "receipt": {"path_hint": str(receipt_path.relative_to(root)), "sha256": digest(receipt_path)},
                "trace": trace_ref, "cache_identity": request["cache_identity"],
                "value_sha256": on["result_sha256"], "guards_sha256": on["guards"]["sha256"],
                "guard_policy": on["guard_policy"], "observer_status": "Active", "interval_ns": trace["interval_ns"],
                "input_dispatch_count": trace["input_dispatch_count"], "dispatches": [dispatch]}]}
        profile_path = root / "provenance/physical-q0/usage-physical-v1.json"
        write_json(profile_path, profile)
        require(not any(name in sys.modules for name in ("cache_usage", "data", "saved_cache")), "owner modules already imported")
        sys.path.insert(0, str(tools))
        owner = importlib.import_module("cache_usage")
        require(Path(owner.__file__).resolve() == tools / "cache_usage.py", "imported another owner")
        for name in ("data", "saved_cache"):
            require(Path(sys.modules[name].__file__).resolve() == tools / (name + ".py"), "imported a foreign owner dependency")
        owner.cohort(root, cohort)
        owner.profile_data(root, profile, root / "5L")
        frequencies = owner.profile_frequencies(root, profile, {"eligible_case_ids": ["q0"]}, binding)
        require(sum(frequencies.values()) == on["saved_application_cache"]["persistent"]["route_hits"], "owner frequency sum differs")
        for name, row in request["owner_sources"].items():
            checked(row)
        summary = {"schema": "vakint.actual-q0-portable-v1-validation.v1", "status": "PASS_CANONICAL_V1_OBSERVED_ROUTE_FREQUENCIES",
            "request_sha256": request_sha, "profile": {"path": str(profile_path.relative_to(pending)), "sha256": digest(profile_path)},
            "canonical_validators": ["cohort", "profile_data", "profile_frequencies -> case_receipt -> physical_receipt"],
            "unique_observed_work_records": len(frequencies), "observed_backing_hits": sum(frequencies.values()),
            "actual_classification_available_preserved": False, "recursive_mapper_certificate": None,
            "proper_descendant_or_frontier_classification_claim": False, "selection_or_export_authorized": False,
            "owner_sources": request["owner_sources"], "owner_source_archives": owner_archives,
            "producer_source": producer_source, "request_source": request_source,
            "actual_all5_source_authority": request["all5_source"],
            "actual_scientific_receipts": {x: request[x]["science"] for x in ("off", "on")},
            "Native_cache_or_master_evaluations": 0, "CAS_or_new_physical_runs": 0}
        write_json(pending / "validation.json", summary)
        publish_new_directory(pending, output)
    except BaseException as error:
        write_json(pending / "failure.json", {"status": "FAIL_PRESERVED_PENDING", "error": repr(error), "no_automatic_retry": True})
        raise
    # Publication has committed. A closed stdout must not recreate a failed
    # pending directory beside an already committed successful output.
    print(json.dumps({"status": summary["status"], "output": str(output), "records": len(frequencies), "hits": sum(frequencies.values())}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--request-sha256", required=True)
    args = parser.parse_args()
    stage(args.request, args.request_sha256)
