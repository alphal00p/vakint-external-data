"""Admit the actual completed Rust tuning measurement; retain outer failure.

Metadata/recorded-trace glue only. No Native, CAS, cache, master evaluation,
selection, exporter or reduction is loaded. The unchanged external-data owner
remains the authority for the portable v1 usage profile.
"""
from pathlib import Path
from collections import Counter
import argparse
import base64
import hashlib
import importlib
import importlib.util
import json
import os
import sys

HELPER_SHA256 = "0f157fb152fa15453af4bc37a9c6496c9f64f1b857eb099944e6255a3eccddc0"
HERE = Path(__file__).resolve().parent
helper_path = HERE / "stage-physical-v1.py"
assert hashlib.sha256(helper_path.read_bytes()).hexdigest() == HELPER_SHA256
spec = importlib.util.spec_from_file_location("actual_physical_metadata_helpers", helper_path)
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
require, load, checked = helpers.require, helpers.load, helpers.checked
digest, copy_input, write_json = helpers.digest, helpers.copy_input, helpers.write_json


def dispatches_from_trace(trace, binding, persistent):
    """Keep observed hits/roots; infer no recursive or proper-descendant scope."""
    require(trace.get("schema") == "vakint.cache-hit-diagnostic.v1"
            and trace.get("success") is True and trace.get("error") is None
            and trace.get("diagnostic_only") is True
            and type(trace.get("interval_ns")) is int and trace["interval_ns"] == 0,
            "trace is incomplete, failed or sampled")
    events = trace.get("events")
    require(isinstance(events, list) and events, "missing recorded events")
    results, previous, active, observer_finished = [], -1, None, False
    names = ("lookups", "misses", "route_hits", "apply_hits", "requested_root_hits", "intermediate_hits")
    for event in events:
        require(event.get("schema") == "vakint.cache-hit-events.v1", "trace schema differs")
        kind = event.get("event")
        if kind == "observer_finish":
            require(event is events[-1] and active is None and results
                    and not observer_finished and event.get("observer_status") == "Active"
                    and "sequence" in event and event["sequence"] is None
                    and event.get("operation_succeeded") is True
                    and type(event.get("interval_ns")) is int and event["interval_ns"] == 0,
                    "observer did not finish completely")
            observer_finished = True
            continue
        required = {"work", "rootwork", "requested_roots", "completed_roots", "persistent", "status"}
        require(required <= set(event), "incomplete native event fields")
        require(kind == "dispatch_finish" or event["status"] == "running", "nonterminal event status differs")
        if event["work"] is not None:
            helpers.observed_work(event["work"], binding["physical_arity"])
        require(kind == "root_collected" or event["rootwork"] is None, "unexpected rootwork outside collection")
        require(type(event["completed_roots"]) is int and 0 <= event["completed_roots"] < (1 << 64)
                and (event["requested_roots"] is None or
                     (type(event["requested_roots"]) is int and 0 <= event["requested_roots"] < (1 << 64))),
                "invalid event root counters")
        require(isinstance(event["persistent"], dict) and set(event["persistent"]) == set(names)
                and all(type(event["persistent"][n]) is int and 0 <= event["persistent"][n] < (1 << 64) for n in names),
                "invalid event persistent counters")
        sequence = event.get("sequence")
        require(type(sequence) is int and sequence > previous, "non-increasing recorded sequence")
        previous = sequence
        require(event.get("family_fingerprint") == binding["family_fingerprint"], "wrong Native family")
        if kind == "dispatch_start":
            require(active is None and not observer_finished, "overlapping dispatch")
            active = {"roots": {}, "hits": Counter()}
        elif kind == "backing_hit":
            require(active is not None, "hit outside dispatch")
            work = helpers.observed_work(event["work"], binding["physical_arity"])
            active["hits"][json.dumps(work, sort_keys=True, separators=(",", ":"))] += 1
        elif kind == "root_collected":
            require(active is not None, "root outside dispatch")
            work = helpers.observed_work(event["rootwork"], binding["physical_arity"])
            require(work["kind"] == "route" and event["work"] is not None
                    and helpers.observed_work(event["work"], binding["physical_arity"]) == work,
                    "collected root/work is not the same Route identity")
            key = json.dumps(work, sort_keys=True, separators=(",", ":"))
            require(key not in active["roots"], "duplicate root")
            active["roots"][key] = work
            require(type(event.get("completed_roots")) is int
                    and event["completed_roots"] == len(active["roots"]), "root counter mismatch")
        elif kind == "dispatch_finish":
            require(active is not None and event.get("status") == "succeeded", "failed/inactive dispatch")
            require(type(event.get("requested_roots")) is int
                    and type(event.get("completed_roots")) is int
                    and event["requested_roots"] == event["completed_roots"] == len(active["roots"]),
                    "incomplete dispatch roots")
            counters = event["persistent"]
            require(set(counters) == set(names)
                    and all(type(counters[n]) is int and 0 <= counters[n] < (1 << 64) for n in names),
                    "invalid dispatch counters")
            route = sum(v for k, v in active["hits"].items() if json.loads(k)["kind"] == "route")
            apply = sum(active["hits"].values()) - route
            require(route == counters["route_hits"] and apply == counters["apply_hits"]
                    and route + apply == counters["lookups"] - counters["misses"]
                    == counters["requested_root_hits"] + counters["intermediate_hits"],
                    "recorded hit frequencies disagree with counters")
            results.append({"ordinal": len(results), "requested_roots": event["requested_roots"],
                            "completed_roots": event["completed_roots"],
                            "collected_roots": [active["roots"][k] for k in sorted(active["roots"])],
                            "persistent": counters,
                            "records": [{"work": json.loads(k), "backing_hits": active["hits"][k]}
                                        for k in sorted(active["hits"])]})
            active = None
        else:
            raise ValueError("unknown recorded trace event: " + str(kind))
    require(observer_finished and active is None and type(trace.get("input_dispatch_count")) is int
            and trace["input_dispatch_count"] == len(results), "missing dispatch or observer boundary")
    require(all(sum(row["persistent"][n] for row in results) == persistent[n] for n in names),
            "trace/accepted measurement counters differ")
    return results


def postflight(request, measurement, summary):
    """Verify the saved terminal facts; never promote the failed outer process."""
    pending, running = load(request["pending_terminal"]), load(request["failed_outer_running"])
    terminal, guard = load(request["outer_kernel_terminal"]), load(request["guard_registration"])
    heartbeat, resources = load(request["final_guard_heartbeat"]), load(request["final_resources"])
    require(running["status"] == "RUNNING" and terminal["original_PIDFD_terminal"] is True
            and terminal["controller_completion_sha256"] == request["failed_outer_running"]["sha256"]
            and terminal["controller_completion"] == running, "failed outer provenance differs")
    require(pending["status"] == "PASS" and pending["signals_sent"] == pending["errors"] == []
            and type(pending["supervisor_exit_code"]) is int and pending["supervisor_exit_code"] == 0
            and pending["worker_pidfd_terminal_observed"] is True
            and pending["supervisor_wait_is_authoritative"] is True
            and pending["worker_wait_evidence"] == measurement["supervision"]
            and running["plan_sha256"] == pending["plan_sha256"]
            and running["root_go_sha256"] == pending["root_go_sha256"],
            "saved unpublished terminal facts disagree")
    outputs = {row["path"]: row["sha256"] for row in pending["outputs"]}
    require(all(outputs.get(request[name]["path"]) == request[name]["sha256"]
                for name in ("measurement", "summary")), "unpublished terminal binds other outputs")
    worker, supervisor = pending["worker"], pending["supervisor"]
    require(measurement["supervision"]["child_pid"] == worker["pid"]
            and measurement["supervision"]["supervisor_pid"] == supervisor["pid"]
            and pending["guard_registration"] == guard and guard["signals_sent"] == []
            and heartbeat["latched_abort"] is False
            and heartbeat["threshold_bytes"] == guard["threshold_bytes"] == 50_000_000_000
            and resources["worker_pidfd_terminal"] is True
            and resources["worker"] == {k: worker[k] for k in ("pid", "start_ticks")},
            "worker/guard terminal identities disagree")
    slots = heartbeat["slots"]
    require(len(slots) == 1, "unexpected guard slot count")
    slot = next(iter(slots.values()))
    require(slot["state"] == "ORIGINAL_PROCESS_TERMINAL"
            and slot["target"] == {"pid": worker["pid"], "start_ticks": worker["start_ticks"],
                                   "supervisor_pid": supervisor["pid"], "supervisor_start_ticks": supervisor["start_ticks"]},
            "guard terminal target differs")
    require(pending["final_resources"]["MemAvailable_bytes"] >= 50_000_000_000
            and pending["final_resources"]["output_filesystem_available_bytes"] >= 100_000_000_000
            and pending["guard_after_actual_wait"]["LoadState"] == "not-found", "final resources/guard closure differs")
    require(summary["complete"] is True and summary["diagnostic_only"] is True
            and summary["provisional"] is False and summary["selection_allowed"] is False
            and summary["final_held_out_comparison"] is False and summary["measurements"] == [measurement]
            and summary["identity"] == measurement["identity"] and len(summary["cases"]) == 1,
            "actual Rust summary differs from measurement")
    require(measurement["success"] is True and measurement["worker_success"] is True
            and measurement["fresh_process"] is True and measurement["native_keys_authenticated"] is True
            and measurement["provisional"] is False and measurement["sample"] == 0
            and measurement["variant"] == "cached" and measurement["identity"]["only_case"] is None
            and measurement["identity"]["suite"] == "tuning"
            and measurement["identity"]["repetitions"] == 1 and measurement["performance_claim_allowed"] is False,
            "not the actual complete frozen tuning measurement")
    return {"outer_controller_status": "FAILED_FINAL_METADATA_PUBLICATION", "outer_controller_PASS": False,
            "unpublished_candidate_promoted": False, "originals_unchanged": True,
            "Rust_supervisor_measurement_admissible_for_owner_check": True}


def stage(request_path, request_sha):
    request = load({"path": str(request_path.resolve()), "sha256": request_sha})
    require(request["schema"] == "vakint.actual-tuning-v1-stage-request.v1", "wrong request schema")
    base = load(request["base_physical_request"])
    tools = helpers.check_owner_sources(base["owner_tools"], base["owner_sources"])
    output = Path(request["output"])
    pending = output.with_name(output.name + ".pending")
    require(output.is_absolute() and not output.exists() and not pending.exists(), "fresh metadata output required")
    for path in request["protected_roots"]:
        source = Path(path).resolve()
        require(not output.resolve().is_relative_to(source) and not source.is_relative_to(output.resolve()),
                "output overlaps an immutable source")
    measurement, summary, worker = (load(request[name]) for name in ("measurement", "summary", "worker"))
    require({k: v for k, v in measurement.items() if k not in ("supervision", "worker_success", "end_to_end_seconds")} == worker
            and measurement["end_to_end_seconds"] == measurement["supervision"]["elapsed_seconds"],
            "Rust supervisor measurement does not preserve worker bytes semantically")
    facts = postflight(request, measurement, summary)
    binding, identity = measurement["cache_statistics"]["binding"], measurement["identity"]
    cache_identity = {k: identity[k] for k in ("cache_sha256", "cache_native_index_identity")}
    require(binding == base["semantic_binding"] and cache_identity == base["cache_identity"]
            and measurement["cache_identity_after"] == cache_identity,
            "actual tuning/all5 binding or read-only identity differs")
    require(measurement["cache_statistics"]["read_backing"] is True
            and measurement["cache_statistics"]["running"] is None
            and measurement["cache_statistics"]["persistent"]["captured_records"] == 0
            and measurement["cache_statistics"]["persistent"]["skipped_records"] == 0,
            "this is not the approved read-only usage run")
    pending.mkdir()
    root = pending / "root"
    root.mkdir()
    try:
        for name, row in request.items():
            if isinstance(row, dict) and set(row) >= {"path", "sha256"}:
                # Every source here is metadata or the already recorded <100MiB trace.
                copy_input(root, row, "provenance/tuning-final/" + name + ".json")
        producer = Path(__file__).resolve()
        copy_input(root, {"path": str(producer), "sha256": digest(producer)}, "provenance/tuning-final/source/stage-tuning-v1.py")
        copy_input(root, {"path": str(helper_path), "sha256": HELPER_SHA256}, "provenance/tuning-final/source/stage-physical-v1.py")
        copy_input(root, {"path": str(request_path.resolve()), "sha256": request_sha}, "provenance/tuning-final/source/request.json")
        for name, row in base["owner_sources"].items():
            copy_input(root, row, "provenance/tuning-final/canonical-owner/" + name)
        for row in base["cohort_archive"]:
            copy_input(root, row, "provenance/actual-two-collector-cohort/" + row["relative"])
        data_refs = {name: copy_input(root, row, "provenance/tuning-final/data/" + name + ".json")
                     for name, row in base["data"].items()}
        for name, relative in (("root", "manifest.json"), ("loop", "5L/manifest.json"),
                               ("application", "5L/ibps/application.json")):
            copy_input(root, base["data"][name], relative)
        all5 = load(base["all5_source"])
        require(all5["cache_native_index_identity"] == cache_identity["cache_native_index_identity"]
                and all5["semantic_binding"] == binding
                and all5["data_manifest_sha256"] == base["data"]["root"]["sha256"], "all5 source differs")
        copy_input(root, base["all5_source"], "provenance/tuning-final/all5-cumulative-report.json")
        trace = load(request["trace"])
        diagnostic = measurement["cache_hit_diagnostic"]
        require(diagnostic["classification_available"] is False and diagnostic["stream_complete"] is True
                and diagnostic["error"] is None and diagnostic["sha256"] == request["trace"]["sha256"],
                "actual diagnostic changed or stronger classification invented")
        dispatches = dispatches_from_trace(trace, binding, measurement["cache_statistics"]["persistent"])
        cohort = load(request["tuning_cohort"])
        require(cohort["main_revision"] == base["Main_revision"]
                and cohort["measurement_executable_sha256"] == identity["executable_sha256"], "wrong actual cohort")
        cohort["data_manifests"] = {name: data_refs[name] for name in ("root", "loop", "application")}
        workload, heldouts = load(request["workload"]), load(request["frozen_heldouts"])
        require(len(workload["tuning"]) == 1 and len(heldouts["held_out"]) == 12,
                "frozen tuning/heldout inventory differs")
        row = workload["tuning"][0]
        require(row["id"] == measurement["case_id"] and request["workload"]["sha256"] == identity["workload_sha256"],
                "wrong actual tuning source")
        snapshot = helpers.unique_json((root / helpers.safe_relative(cohort["main_source_snapshot"]["path_hint"])).read_bytes())
        require(snapshot["files"]["crates/vakint/examples/build_cache/frozen-public-suites.json"]["sha256"]
                == request["frozen_heldouts"]["sha256"], "compiled heldout inventory differs")
        documents = [{"sha256": request[name]["sha256"],
                      "json_bytes_base64": base64.b64encode(checked(request[name]).read_bytes()).decode()}
                     for name in ("workload", "frozen_heldouts")]
        profile = {"schema": "vakint.cache-record-usage-profile.v1", "semantic_binding": binding,
                   "compiled_cohort": cohort,
                   "data": {"root_manifest_sha256": base["data"]["root"]["sha256"],
                            "loop_manifest_sha256": base["data"]["loop"]["sha256"],
                            "application_sha256": base["data"]["application"]["sha256"]},
                   "eligibility_documents": documents,
                   "cases": [{"case_id": row["id"], "role": "tuning", "input_sha256": measurement["input_sha256"],
                              "public_input_source_sha256": hashlib.sha256(row["public_input"].encode()).hexdigest(),
                              "role_evidence": {"document_sha256": request["workload"]["sha256"], "json_pointer": "/tuning/0"},
                              "receipt": {"path_hint": "provenance/tuning-final/measurement.json", "sha256": request["measurement"]["sha256"]},
                              "trace": {"path_hint": "provenance/tuning-final/trace.json", "sha256": request["trace"]["sha256"]},
                              "cache_identity": cache_identity, "value_sha256": measurement["value_sha256"],
                              "guards_sha256": measurement["guards_sha256"], "guard_policy": "canonical-full-sorted-deduplicated",
                              "observer_status": "Active", "interval_ns": trace["interval_ns"],
                              "input_dispatch_count": trace["input_dispatch_count"], "dispatches": dispatches}]}
        profile_path = root / "provenance/tuning-final/usage-tuning-v1.json"
        write_json(profile_path, profile)
        require(not any(name in sys.modules for name in ("cache_usage", "data", "saved_cache")), "owner already imported")
        sys.path.insert(0, str(tools))
        owner = importlib.import_module("cache_usage")
        require(Path(owner.__file__).resolve() == tools / "cache_usage.py", "wrong owner import")
        for name in ("data", "saved_cache"):
            require(Path(sys.modules[name].__file__).resolve() == tools / (name + ".py"), "wrong owner dependency")
        owner.cohort(root, cohort)
        owner.profile_data(root, profile, root / "5L")
        frequencies = owner.profile_frequencies(root, profile, {"eligible_case_ids": [row["id"]]}, binding)
        require(sum(frequencies.values()) == sum(measurement["cache_statistics"]["persistent"][n]
                                                 for n in ("route_hits", "apply_hits")), "owner hit sum differs")
        helpers.check_owner_sources(base["owner_tools"], base["owner_sources"])
        result = {"schema": "vakint.actual-tuning-portable-v1-validation.v1", "status": "PASS_CANONICAL_V1_OBSERVED_FREQUENCIES",
                  "request_sha256": request_sha, "profile": {"path": str(profile_path.relative_to(pending)), "sha256": digest(profile_path)},
                  "outer_failure_postflight": facts, "unique_observed_work_records": len(frequencies),
                  "observed_backing_hits": sum(frequencies.values()), "classification_available_preserved": False,
                  "recursive_mapper_certificate": None, "proper_descendant_classification_claim": False,
                  "new_Rust_Native_IBP_CAS_cache_reads": 0, "selection_or_export_authorized": False}
        write_json(pending / "validation.json", result)
        helpers.publish_new_directory(pending, output)
    except BaseException as error:
        write_json(pending / "failure.json", {"status": "FAIL_PRESERVED_PENDING", "error": repr(error), "no_retry": True})
        raise
    print(json.dumps({"status": result["status"], "output": str(output), "records": len(frequencies), "hits": sum(frequencies.values())}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--request-sha256", required=True)
    args = parser.parse_args()
    stage(args.request, args.request_sha256)
