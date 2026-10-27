"""Synthetic file contracts only: no Native export, import or mathematical proof."""

import base64
import copy
import gzip
import hashlib
import json
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import cache_usage
import data
import saved_cache
import test_saved_cache


class UsageSelectedAdmissionTests(unittest.TestCase):
    def setUp(self):
        test_saved_cache.SavedCacheAdmissionTests.setUp(self)
        self.repo = self.root
        self.root = self.repo / "5L"
        self.root.mkdir()
        for path in self.repo.iterdir():
            if path != self.root:
                shutil.move(path, self.root / path.name)
        self.path = self.root / "cache/prepared.rrcache.gz"
        self.binding = self.manifest["cache"]["binding"]
        self.index = {
            "schema": "vakint.native-cache-index-identity.v1",
            "layout": "pack",
            "indexes": {"cache.rrindex": {"bytes": 12, "sha256": "a" * 64}},
        }
        self.index["sha256"] = hashlib.sha256(
            json.dumps(self.index, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        self.producer = {
            "schema": "vakint.cumulative-native-cache-report.v1",
            "cache_sha256": None,
            "cache_native_index_identity": self.index,
            "data_manifest_sha256": "0" * 64,
            "semantic_binding": self.binding,
            "sources": [{"id": "synthetic-prefix", "scope": "committed-prefix"}],
        }
        self.inventory = {"synthetic": True, "cache_native_index_identity": self.index}
        source_sha = "7" * 64
        main = {
            "schema": "vakint.actual-tracked-source-snapshot.v1",
            "revision": "1" * 40,
            "files": {
                "crates/vakint/examples/measure_cache.rs": {"sha256": source_sha}
            },
        }
        native = {
            "schema": "vakint.actual-tracked-source-snapshot.v1",
            "revision": "2" * 40,
            "files": {},
        }
        main_ref, native_ref = (
            self.save("main.json", main),
            self.save("native.json", native),
        )
        self.compiled = {
            "main_revision": main["revision"],
            "native_revision": native["revision"],
            "kernel_revision": "3" * 40,
            "main_source_snapshot_sha256": main_ref["sha256"],
            "native_source_snapshot_sha256": native_ref["sha256"],
            "measurement_executable_sha256": "4" * 64,
            "collector_source_sha256": source_sha,
            "profile": "release",
            "rustc": "synthetic-rustc",
            "main_source_snapshot": self.hint(main_ref),
            "native_source_snapshot": self.hint(native_ref),
        }
        stamps = {
            stamp: self.compiled[name]
            for name, stamp in cache_usage.COHORT_FIELDS.items()
        }
        self.artifacts = {
            "status": "BUILT_AND_ALL_FIVE_STAMPS_AUTHENTICATED",
            "source_head": main["revision"],
            "profile": "release",
            "compile_proof": dict(
                stamps,
                VAKINT_CACHE_BUILD_PROFILE="release",
                VAKINT_CACHE_BUILD_RUSTC="synthetic-rustc",
            ),
            "artifacts": {
                "measure_cache": {
                    "sha256": "4" * 64,
                    "all_five_actual_env_dep_stamps": stamps,
                }
            },
        }
        self.compiled["collector_artifacts"] = self.hint(
            self.save("artifacts.json", self.artifacts)
        )
        application = self.save_bytes(
            "data/application.json", (self.root / "ibps/application.json").read_bytes()
        )
        loop = {
            "schema": data.LOOP_SCHEMA,
            "version": "v0.0.0",
            "loop_count": 5,
            "files": {
                "ibps/application.json": data.file_record(
                    self.root / "ibps/application.json"
                )
            },
        }
        loop_ref = self.save("data/loop.json", loop)
        release = {
            "schema": data.ROOT_SCHEMA,
            "version": "v0.0.0",
            "loop_packs": [
                {
                    "loop_count": 5,
                    "manifest": "5L/manifest.json",
                    "manifest_sha256": loop_ref["sha256"],
                }
            ],
        }
        root_ref = self.save("data/root.json", release)
        self.data_root_sha256 = root_ref["sha256"]
        self.producer["data_manifest_sha256"] = self.data_root_sha256
        self.compiled["data_manifests"] = {
            "root": self.hint(root_ref),
            "loop": self.hint(loop_ref),
            "application": self.hint(application),
        }
        document = {
            "schema": "vakint.five-loop-cache-workload.v1",
            "tuning": [{"id": "tune", "public_input": "vacuum( 1 )"}],
            "held_out": [{"id": "final", "public_input": "vacuum( 2 )"}],
        }
        self.document = document
        embedded = self.embed(document)
        self.route = {"kind": "route", "powers": [1] * 15}
        self.apply = {"kind": "apply", "owner_sector": [True] * 15, "powers": [1] * 15}
        persistent = {
            "lookups": 7,
            "misses": 2,
            "route_hits": 2,
            "apply_hits": 3,
            "requested_root_hits": 1,
            "intermediate_hits": 4,
        }
        self.case = {
            "case_id": "tune",
            "role": "tuning",
            "input_sha256": "c" * 64,
            "public_input_source_sha256": hashlib.sha256(
                document["tuning"][0]["public_input"].encode()
            ).hexdigest(),
            "role_evidence": {
                "document_sha256": embedded["sha256"],
                "json_pointer": "/tuning/0",
            },
            "receipt": {},
            "trace": {"sha256": "d" * 64},
            "cache_identity": {
                "cache_sha256": data.digest(self.path),
                "cache_native_index_identity": None,
            },
            "value_sha256": "e" * 64,
            "guards_sha256": "f" * 64,
            "guard_policy": "canonical-full-sorted-deduplicated",
            "observer_status": "Active",
            "interval_ns": 0,
            "input_dispatch_count": 1,
            "dispatches": [
                {
                    "ordinal": 0,
                    "requested_roots": 1,
                    "completed_roots": 1,
                    "collected_roots": [self.route],
                    "persistent": persistent,
                    "records": [
                        {"work": self.route, "backing_hits": 2},
                        {"work": self.apply, "backing_hits": 3},
                    ],
                }
            ],
        }
        self.profile = {
            "schema": "vakint.cache-record-usage-profile.v1",
            "semantic_binding": self.binding,
            "compiled_cohort": self.compiled,
            "data": {
                "root_manifest_sha256": root_ref["sha256"],
                "loop_manifest_sha256": loop_ref["sha256"],
                "application_sha256": data.digest(self.root / "ibps/application.json"),
            },
            "eligibility_documents": [embedded],
            "cases": [self.case],
        }
        self.receipt = {
            "success": True,
            "worker_success": True,
            "fresh_process": True,
            "case_id": "tune",
            "variant": "cached",
            "supervision": {
                "success": True,
                "exit_code": 0,
                "deadline_exhausted": False,
            },
            "input_sha256": self.case["input_sha256"],
            "value_sha256": self.case["value_sha256"],
            "guards_sha256": self.case["guards_sha256"],
            "identity": {
                "data_manifest_sha256": root_ref["sha256"],
                "workload_sha256": embedded["sha256"],
                "executable_sha256": "4" * 64,
                "compiled_driver_sha256": source_sha,
                "build_git_revision": main["revision"],
                "build_profile": "release",
                "build_rustc": "synthetic-rustc",
                "cache_sha256": data.digest(self.path),
                "cache_native_index_identity": None,
                "cache_hit_diagnostic": True,
                "owner_proof": None,
            },
            "cache_statistics": {
                "binding": self.binding,
                "persistent": copy.deepcopy(persistent),
            },
            "cache_hit_diagnostic": {
                "stream_complete": True,
                "diagnostic_only": True,
                "interval_ns": 0,
                "error": None,
                "sha256": "d" * 64,
            },
        }
        self.keys = {
            "schema": "vakint.cache-record-selection.v1",
            "semantic_binding": self.binding,
            "usage_profile_sha256": "",
            "eligible_case_ids": ["tune"],
            "keys": [self.route, self.apply],
            "selection": {
                "method": "synthetic frequency selection",
                "max_compressed_bytes": 95_000_000,
            },
        }
        exporter_cohort, exporter_artifact = self.native_build()
        self.raw = {
            "schema": "vakint.strict-light-cache-native-validation.v1",
            "success": True,
            "semantic_binding": self.binding,
            "source_cache_native_index_identity": self.index,
            "cache_sha256": data.digest(self.path),
            "cache_identity": self.identity,
            "decoded_sha256": self.decoded_hash,
            "compiled_cohort": exporter_cohort,
            "collector_artifacts": exporter_artifact,
            "executable_sha256": "5" * 64,
            "selected_records": 2,
            "reimported_records": 2,
            "complete_records": 2,
            "missing_keys": 0,
            "partial_records": 0,
            "exact_record_and_ordered_guard_equality": True,
            "declared_terminal_validation": True,
            "source_unchanged": True,
            "codec_state_format": 6,
        }
        self.compress = False
        self.seal()

    @staticmethod
    def hint(reference):
        return {"path_hint": reference["path"], "sha256": reference["sha256"]}

    @staticmethod
    def embed(document):
        raw = (json.dumps(document, indent=2) + "\n").encode()
        return {
            "sha256": hashlib.sha256(raw).hexdigest(),
            "json_bytes_base64": base64.b64encode(raw).decode(),
        }

    def save(self, name, document):
        raw = (json.dumps(document, indent=2) + "\n").encode()
        return self.save_bytes(name, raw)

    def save_bytes(self, name, raw):
        path = self.repo / "provenance/light" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(gzip.compress(raw, mtime=0) if name.endswith(".gz") else raw)
        return {
            "path": path.relative_to(self.repo).as_posix(),
            "sha256": data.digest(path),
        }

    def native_build(self):
        source_bytes = (
            b"// Synthetic source framing fixture; never compiled or executed.\n"
        )
        source = self.save_bytes("native-source/src/main.rs", source_bytes)
        documentation_bytes = b"= Synthetic producer provenance\n"
        documentation = self.save_bytes(
            "native-source/PRODUCER.typ", documentation_bytes
        )
        native = {
            "schema": "native.git-source-tree-identity.v1",
            "clean": True,
            "codec_state_format": 6,
            "revision": "2" * 40,
            "kernel_revision": "3" * 40,
        }
        identity = {
            "schema": "native.private-layered-helper-source-identity.v1",
            "files": {"src/main.rs": source["sha256"]},
            "native_identity": native,
        }

        def canonical(value):
            return hashlib.sha256(
                json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()

        compiled = {
            "main_revision": "2" * 40,
            "native_revision": "2" * 40,
            "kernel_revision": "3" * 40,
            "main_source_snapshot_sha256": canonical(identity),
            "native_source_snapshot_sha256": canonical(native),
            "source_identity": identity,
            "collector_source_sha256": source["sha256"],
            "measurement_executable_sha256": "5" * 64,
        }
        freeze = self.save(
            "native-source-freeze.json",
            {
                "files": {
                    "src/main.rs": dict(source, bytes=len(source_bytes)),
                    "PRODUCER.typ": dict(documentation, bytes=len(documentation_bytes)),
                }
            },
        )
        artifact = {
            "schema": "vakint.native-selected-cache-producer-artifact.v1",
            "state": "PASS_BUILD_PARSER_CLIPPY_BUILDINFO_NO_5L_ACTIVATION",
            "gates": {
                name: {"exit_code": 0}
                for name in ("parser-tests", "clippy", "build", "build-info")
            },
            "compiled_cohort": compiled,
            "stamps": {
                stamp: compiled[name]
                for name, stamp in cache_usage.COHORT_FIELDS.items()
            },
            "binary": {"sha256": "5" * 64, "bytes": 100, "ELF": True},
            "source_freeze": dict(
                freeze, bytes=(self.repo / freeze["path"]).stat().st_size
            ),
            "source_unchanged": True,
            "native_and_kernel_clean": True,
        }
        return compiled, self.save("native-artifact.json", artifact)

    def seal(self):
        self.case["receipt"] = self.hint(self.save("case.json", self.receipt))
        suffix = ".json.gz" if self.compress else ".json"
        profile = self.save("profile" + suffix, self.profile)
        self.keys["usage_profile_sha256"] = profile["sha256"]
        keys = self.save("keys" + suffix, self.keys)
        inventory = self.save("inventory" + suffix, self.inventory)
        self.raw.update(
            selected_keys_sha256=keys["sha256"],
            usage_profile_sha256=profile["sha256"],
            source_inventory_sha256=inventory["sha256"],
        )
        self.metadata = {
            "schema": "vakint.external-data.saved-cache.v1",
            "strict": True,
            "coverage_claim": False,
            "selection": {
                "kind": "usage-selected-strict-snapshot",
                "source": {
                    "producer": self.save("producer.json", self.producer),
                    "data_manifest_sha256": self.data_root_sha256,
                    "cache_native_index_identity": self.index,
                    "inventory": inventory,
                },
                "keys": keys,
                "unique_keys": 2,
                "usage_profile": profile,
                "allowed_input_classes": ["tuning", "physical-example"],
                "final_held_out_used": False,
                "validation": self.save("native-validation.json", self.raw),
            },
        }
        data.write_json(self.root / "cache.json", self.metadata)

    def validate(self):
        return saved_cache.validate(self.root, self.manifest)

    def test_usage_variant_recomputes_admission_without_finite_workload_claims(self):
        with patch.object(saved_cache, "TARGET_COMPRESSED", 1):
            admission = self.validate()
        self.assertTrue(admission["accepted"])
        self.assertEqual(admission["selected_unique_keys"], 2)
        self.assertEqual(admission["eligible_profile_unique_keys"], 2)
        self.assertTrue(all(admission["checks"].values()))
        self.assertNotEqual(
            self.case["input_sha256"], self.case["public_input_source_sha256"]
        )
        self.assertNotIn("preparation_report", self.metadata)
        self.assertNotIn("final_build_elapsed_seconds", self.metadata)

    def test_compressed_source_summaries_are_supported(self):
        self.compress = True
        self.seal()
        self.assertTrue(self.validate()["accepted"])

    def test_frozen_authority_and_actual_invocation_documents_can_differ(self):
        authority = copy.deepcopy(self.document)
        authority["schema"] = "vakint.five-loop-frozen-public-suites.v1"
        embedded = self.embed(authority)
        self.profile["eligibility_documents"].append(embedded)
        self.case["role_evidence"]["document_sha256"] = embedded["sha256"]
        self.seal()
        self.assertTrue(self.validate()["accepted"])
        self.receipt["identity"]["workload_sha256"] = "8" * 64
        self.seal()
        with self.assertRaisesRegex(ValueError, "invocation workload"):
            self.validate()

    def test_native_index_cache_projection_is_checked_without_reading_native_files(
        self,
    ):
        projection = {"cache_sha256": None, "cache_native_index_identity": self.index}
        self.case["cache_identity"] = copy.deepcopy(projection)
        self.receipt["identity"].update(projection)
        self.seal()
        self.assertTrue(self.validate()["accepted"])
        self.case["cache_identity"]["cache_native_index_identity"]["sha256"] = "0" * 64
        self.receipt["identity"]["cache_native_index_identity"] = self.case[
            "cache_identity"
        ]["cache_native_index_identity"]
        self.seal()
        with self.assertRaisesRegex(ValueError, "index commitment"):
            self.validate()

    def test_q0_anchor_requires_the_same_complete_measure_cache_receipt(self):
        original = (
            Path(__file__).resolve().parents[1]
            / "5L/benchmarks/zero-momentum/prepared-input.json"
        )
        raw = original.read_bytes()
        prepared = json.loads(raw)
        embedded_prepared = {
            "sha256": hashlib.sha256(raw).hexdigest(),
            "json_bytes_base64": base64.b64encode(raw).decode(),
        }
        target = self.root / "benchmarks/zero-momentum/prepared-input.json"
        target.parent.mkdir(parents=True)
        target.write_bytes(raw)
        physical = {
            "schema": "vakint.physical-cache-usage-source-inventory.v1",
            "cases": [
                {
                    "id": "q0",
                    "source_job_id": "q0",
                    "role": "physical-example",
                    "projection": "zero-momentum-metric",
                    "definition": prepared["definition"],
                    "input_source_kind": "prepared-vakint-input.symbolica-file-bytes",
                    "public_input_source_sha256": prepared["input"]["sha256"],
                    "public_input_source_bytes": prepared["input"]["bytes"],
                    "prepared_manifest_sha256": embedded_prepared["sha256"],
                    "source_job_config_sha256": "a" * 64,
                }
            ],
            "prepared_manifest_documents": [embedded_prepared],
        }
        embedded = self.embed(physical)
        self.profile["eligibility_documents"].append(embedded)
        self.case.update(
            case_id="q0",
            role="physical-example",
            public_input_source_sha256=prepared["input"]["sha256"],
            role_evidence={
                "document_sha256": embedded["sha256"],
                "json_pointer": "/cases/0",
            },
        )
        invocation = copy.deepcopy(self.document)
        public_input = (original.parent / "vakint-input.symbolica").read_text()
        invocation["tuning"] = [{"id": "q0", "public_input": public_input}]
        invocation_document = self.embed(invocation)
        self.profile["eligibility_documents"].append(invocation_document)
        self.receipt["case_id"] = "q0"
        self.receipt["identity"]["workload_sha256"] = invocation_document["sha256"]
        self.keys["eligible_case_ids"] = ["q0"]
        self.seal()
        self.assertTrue(self.validate()["accepted"])
        accepted = copy.deepcopy(self.receipt)
        self.receipt = {
            "projection": "zero-momentum-metric",
            "synthetic_sampled_snapshot": True,
        }
        self.seal()
        with self.assertRaisesRegex(ValueError, "accepted case identity"):
            self.validate()
        self.receipt = accepted
        physical["cases"][0]["projection"] = "quadratic"
        embedded = self.embed(physical)
        self.profile["eligibility_documents"][-2] = embedded
        self.case["role_evidence"]["document_sha256"] = embedded["sha256"]
        self.seal()
        with self.assertRaisesRegex(ValueError, "complete zero-momentum"):
            self.validate()

    def physical_fixture(self):
        """Synthetic source evidence, never an executed physical reduction."""
        original = (
            Path(__file__).resolve().parents[1]
            / "5L/benchmarks/zero-momentum/prepared-input.json"
        )
        raw = original.read_bytes()
        prepared = json.loads(raw)
        target = self.root / "benchmarks/zero-momentum/prepared-input.json"
        target.parent.mkdir(parents=True)
        target.write_bytes(raw)
        physical = {
            "schema": "vakint.physical-cache-usage-source-inventory.v1",
            "cases": [
                {
                    "id": "q0",
                    "source_job_id": "q0",
                    "role": "physical-example",
                    "projection": "zero-momentum-metric",
                    "definition": prepared["definition"],
                    "input_source_kind": "prepared-vakint-input.symbolica-file-bytes",
                    "public_input_source_sha256": prepared["input"]["sha256"],
                    "public_input_source_bytes": prepared["input"]["bytes"],
                    "prepared_manifest_sha256": hashlib.sha256(raw).hexdigest(),
                    "source_job_config_sha256": "a" * 64,
                }
            ],
            "prepared_manifest_documents": [
                {
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "json_bytes_base64": base64.b64encode(raw).decode(),
                }
            ],
        }
        anchor = self.embed(physical)
        self.profile["eligibility_documents"].append(anchor)
        self.case.update(
            case_id="q0",
            role="physical-example",
            input_sha256=prepared["input"]["sha256"],
            public_input_source_sha256=prepared["input"]["sha256"],
            role_evidence={
                "document_sha256": anchor["sha256"],
                "json_pointer": "/cases/0",
            },
        )
        self.keys["eligible_case_ids"] = ["q0"]
        main = cache_usage.source_json(
            self.repo,
            {
                "path": self.compiled["main_source_snapshot"]["path_hint"],
                "sha256": self.compiled["main_source_snapshot"]["sha256"],
            },
        )
        main["files"]["crates/vakint/examples/five_loop_qcd_ladder.rs"] = main[
            "files"
        ].pop("crates/vakint/examples/measure_cache.rs")
        helpers = {path: "6" * 64 for path in cache_usage.PHYSICAL_COLLECTOR_HELPERS}
        main["files"].update(
            {path: {"sha256": checksum} for path, checksum in helpers.items()}
        )
        main_ref = self.save("main.json", main)
        self.compiled.update(
            collector="five_loop_qcd_ladder",
            collector_helper_sources_sha256=helpers,
            main_source_snapshot=self.hint(main_ref),
            main_source_snapshot_sha256=main_ref["sha256"],
        )
        stamps = {
            stamp: self.compiled[name]
            for name, stamp in cache_usage.COHORT_FIELDS.items()
        }
        binary = self.artifacts["artifacts"].pop("measure_cache")
        binary["all_five_actual_env_dep_stamps"] = stamps
        self.artifacts["artifacts"]["five_loop_qcd_ladder"] = binary
        self.artifacts["compile_proof"].update(stamps)
        self.compiled["collector_artifacts"] = self.hint(
            self.save("artifacts.json", self.artifacts)
        )
        statistics = copy.deepcopy(self.receipt["cache_statistics"])
        statistics.update(read_backing=True, running=None)
        statistics["persistent"].update(captured_records=0, skipped_records=0)
        normal = {
            "schema": "vakint.qcd-ladder.benchmark.v1",
            "projection": "zero-momentum-metric",
            "input_mode": "prepared",
            "fresh_native_preparation": False,
            "prepared_input": {
                "manifest_sha256": hashlib.sha256(raw).hexdigest(),
                "manifest": prepared,
            },
            "input_sha256": self.case["input_sha256"],
            "input_canonical_sha256": self.case["input_sha256"],
            "input_bytes": prepared["input"]["bytes"],
            "consumer_fixture_sources_sha256": dict(
                prepared["scientific_sources_sha256"], **{"mod.rs": "8" * 64}
            ),
            "master_mode": "retain",
            "guard_policy": "canonical-full-sorted-deduplicated",
            "retained_result_available": True,
            "reduction_completed": True,
            "cache_hit_diagnostic_enabled": False,
            "diagnostic_only": False,
            "performance_claim": False,
            "warm_requested": False,
            "running_cache_path": None,
            "running_cache_attached": False,
            "running_cache_capture_only": False,
            "persistent_cache_attached": True,
            "persistent_cache_policy": "manual-five-loop-only",
            "persistent_cache_attachments_before": {str(i): False for i in range(1, 6)},
            "persistent_cache_attachments_during_evaluation": {
                str(i): i == 5 for i in range(1, 6)
            },
            "compiled_cohort": {
                name: self.compiled[name]
                for name in (*cache_usage.COHORT_FIELDS, "profile", "rustc")
            },
            "executable_sha256": self.compiled["measurement_executable_sha256"],
            "collector_source_sha256": self.compiled["collector_source_sha256"],
            "collector_helper_sources_sha256": helpers,
            "source_commit": self.compiled["main_revision"],
            "source_dirty": False,
            "data_manifest_sha256": self.profile["data"]["root_manifest_sha256"],
            "cache_identity": copy.deepcopy(self.case["cache_identity"]),
            "cache_identity_after": copy.deepcopy(self.case["cache_identity"]),
            "catalogue_closure": {
                "closed": True,
                "unknown_count": 0,
                "unknown_preview": [],
                "unknown_sha256": "0" * 64,
            },
            "guards": {
                "count": 1,
                "includes_preparation_conditions": True,
                "sha256": self.case["guards_sha256"],
            },
            "result_sha256": self.case["value_sha256"],
            "result_bytes": 123,
            "families": {"master": "synthetic-family"},
            "saved_application_cache": statistics,
        }
        diagnostic = copy.deepcopy(normal)
        diagnostic.update(
            cache_hit_diagnostic_enabled=True,
            diagnostic_only=True,
            cache_hit_diagnostic=copy.deepcopy(self.receipt["cache_hit_diagnostic"]),
        )
        self.physical_reports = [normal, diagnostic]
        self.physical_launches, self.physical_completions = [], []
        for index in range(2):
            process = {"pid": index + 100, "start_ticks": 1000 + index}
            argv = [
                "/synthetic/collector",
                "--work-dir",
                f"/synthetic/output-{index}",
                "--cache",
                "/synthetic/heavy.gz",
                "--prepared-input",
                "/synthetic/q0",
            ]
            if index:
                argv.append("--classify-cache-hits")
            self.physical_launches.append(
                {
                    "collector": process,
                    "supervisor": {"pid": 90, "start_ticks": 900},
                    "argv": argv,
                    "config_sha256": str(index + 1) * 64,
                    "performance_eligible": False,
                    "automatic_retry": False,
                    "runtime_hard_cap": None,
                }
            )
            self.physical_completions.append(
                {
                    "collector": process,
                    "collector_exit_code": 0,
                    "process_zero_acceptance": True,
                    "functional_acceptance": True,
                    "native_child_restarted_or_signalled": False,
                    "performance_eligible": False,
                    "config_sha256": str(index + 1) * 64,
                    "post_executable": {
                        "path": argv[0],
                        "sha256": normal["executable_sha256"],
                        "bytes": 100,
                    },
                }
            )
        self.seal_physical()

    def seal_physical(self):
        self.receipt = {"schema": "vakint.physical-cache-usage-receipt.v1"}
        for index, prefix in enumerate(("reference_", "")):
            report, completion = (
                self.physical_reports[index],
                self.physical_completions[index],
            )
            report_ref = self.save(prefix + "benchmark.json", report)
            completion["outputs"] = {
                "benchmark_sha256": report_ref["sha256"],
                "result_sha256": report["result_sha256"],
                "result_bytes": report["result_bytes"],
                "guards_sha256": report["guards"]["sha256"],
                "guards_count": report["guards"]["count"],
                "unknown_sha256": report["catalogue_closure"]["unknown_sha256"],
                "unknown_count": report["catalogue_closure"]["unknown_count"],
            }
            completion["terminal_artifacts"] = {
                name: {
                    "exists": True,
                    "sha256": checksum,
                    "bytes": report["result_bytes"]
                    if name == "result.symbolica"
                    else 100,
                }
                for name, checksum in {
                    "benchmark.json": report_ref["sha256"],
                    "result.symbolica": report["result_sha256"],
                    "nonzero-conditions.symbolica": report["guards"]["sha256"],
                    "unknown-masters.json": report["catalogue_closure"][
                        "unknown_sha256"
                    ],
                }.items()
            }
            completion["terminal_artifacts"]["benchmark.json"]["bytes"] = (
                (self.repo / report_ref["path"]).stat().st_size
            )
            self.receipt[prefix + "benchmark"] = self.hint(report_ref)
            self.receipt[prefix + "completion"] = self.hint(
                self.save(prefix + "completion.json", completion)
            )
            self.receipt[prefix + "launch"] = self.hint(
                self.save(prefix + "launch.json", self.physical_launches[index])
            )
        self.seal()

    def test_physical_receipt_reuses_common_lossless_usage_without_fake_workload(self):
        self.physical_fixture()
        self.assertTrue(self.validate()["accepted"])
        self.assertFalse(
            any(
                document.get("tuning", [{}])[0].get("id") == "q0"
                for document in cache_usage.embedded_eligibility(self.profile)[
                    0
                ].values()
                if document.get("tuning")
            )
        )
        self.assertEqual(
            self.case["input_sha256"], self.case["public_input_source_sha256"]
        )

    def test_physical_source_identity_cache_and_result_parity_fail_closed(self):
        self.physical_fixture()
        original = copy.deepcopy(self.physical_reports)
        for field, value, message in (
            ("input_canonical_sha256", "9" * 64, "canonical prepared input"),
            ("executable_sha256", "9" * 64, "cohort, data or immutable cache"),
            ("cache_identity_after", {}, "cohort, data or immutable cache"),
            ("result_sha256", "9" * 64, "result, complete guards"),
            ("guard_policy", "native-ordered-vector", "retained read-only"),
            ("master_mode", "numerical", "retained read-only"),
            ("warm_requested", True, "retained read-only"),
            ("running_cache_attached", True, "retained read-only"),
            ("performance_claim", True, "retained read-only"),
            ("diagnostic_only", False, "retained read-only"),
        ):
            with self.subTest(field=field):
                self.physical_reports = copy.deepcopy(original)
                self.physical_reports[1][field] = value
                self.seal_physical()
                with self.assertRaisesRegex(ValueError, message):
                    self.validate()

    def test_physical_normal_reference_and_actual_process_are_required(self):
        self.physical_fixture()
        self.physical_launches[1]["collector"] = self.physical_launches[0]["collector"]
        self.physical_completions[1]["collector"] = self.physical_launches[0][
            "collector"
        ]
        self.seal_physical()
        with self.assertRaisesRegex(ValueError, "fresh same-cohort"):
            self.validate()
        self.physical_completions[1]["collector_exit_code"] = True
        self.seal_physical()
        with self.assertRaisesRegex(ValueError, "actual process supervision"):
            self.validate()

    def test_physical_helper_source_closure_is_authenticated(self):
        self.physical_fixture()
        self.compiled["collector_helper_sources_sha256"] = {}
        self.seal()
        with self.assertRaisesRegex(ValueError, "helpers differ"):
            self.validate()

    def test_physical_dispatch_and_trace_keep_the_common_strict_validator(self):
        self.physical_fixture()
        self.physical_reports[1]["cache_hit_diagnostic"]["stream_complete"] = False
        self.seal_physical()
        with self.assertRaisesRegex(ValueError, "lossless trace"):
            self.validate()
        self.physical_reports[1]["cache_hit_diagnostic"]["stream_complete"] = True
        self.physical_reports[1]["saved_application_cache"]["persistent"][
            "captured_records"
        ] = 1
        self.seal_physical()
        with self.assertRaisesRegex(ValueError, "must not capture"):
            self.validate()

    def test_physical_supervision_cannot_be_replaced_with_success_booleans(self):
        self.physical_fixture()
        original = copy.deepcopy(self.physical_completions)
        for field, value, message in (
            ("collector", {}, "actual process supervision"),
            ("config_sha256", "9" * 64, "actual process supervision"),
            ("collector_exit_code", False, "actual process supervision"),
            ("collector_exit_code", 1, "actual process supervision"),
            ("functional_acceptance", 1, "actual process supervision"),
            ("native_child_restarted_or_signalled", True, "actual process supervision"),
            ("post_executable", {}, "executable or diagnostic policy"),
        ):
            with self.subTest(field=field, value=value):
                self.physical_completions = copy.deepcopy(original)
                self.physical_completions[1][field] = value
                self.seal_physical()
                with self.assertRaisesRegex(ValueError, message):
                    self.validate()
        self.physical_completions = copy.deepcopy(original)
        self.seal_physical()
        completion = copy.deepcopy(self.physical_completions[1])
        completion["outputs"]["guards_sha256"] = "9" * 64
        self.receipt["completion"] = self.hint(self.save("completion.json", completion))
        self.seal()
        with self.assertRaisesRegex(ValueError, "complete retained files"):
            self.validate()

    def test_physical_reference_must_use_the_same_settings_and_have_no_unknowns(self):
        self.physical_fixture()
        original = copy.deepcopy(self.physical_reports)
        for change, message in (
            ({"catalogue_closure": {"closed": False}}, "catalogue closure"),
            (
                {
                    "guards": {
                        "count": 1,
                        "includes_preparation_conditions": False,
                        "sha256": self.case["guards_sha256"],
                    }
                },
                "complete guards",
            ),
            ({"cache_hit_diagnostic": {}}, "normal reference"),
            ({"families": {"other": "family"}}, "normal reference"),
            ({"compiled_cohort": {}}, "cohort, data or immutable cache"),
        ):
            with self.subTest(change=change):
                self.physical_reports = copy.deepcopy(original)
                self.physical_reports[0].update(change)
                # Keep enough completed-output fields for the synthetic receipt
                # writer; the validator still must reject the altered closure.
                if "catalogue_closure" in change:
                    self.physical_reports[0]["catalogue_closure"].update(
                        unknown_count=0, unknown_sha256="0" * 64, unknown_preview=[]
                    )
                self.seal_physical()
                with self.assertRaisesRegex(ValueError, message):
                    self.validate()
        self.physical_reports = copy.deepcopy(original)
        self.physical_launches[1]["argv"].extend(
            ["--coefficient-representation", "factorized"]
        )
        self.seal_physical()
        with self.assertRaisesRegex(ValueError, "normal reference"):
            self.validate()

    def test_physical_native_index_identity_is_supported_without_reading_cache_payloads(
        self,
    ):
        self.physical_fixture()
        projection = {"cache_sha256": None, "cache_native_index_identity": self.index}
        self.case["cache_identity"] = copy.deepcopy(projection)
        for report in self.physical_reports:
            report["cache_identity"] = copy.deepcopy(projection)
            report["cache_identity_after"] = copy.deepcopy(projection)
        self.seal_physical()
        self.assertTrue(self.validate()["accepted"])
        self.physical_reports[0]["cache_identity_after"]["cache_native_index_identity"][
            "sha256"
        ] = "9" * 64
        self.seal_physical()
        with self.assertRaisesRegex(ValueError, "immutable cache"):
            self.validate()

    def test_physical_receipt_still_requires_unsampled_exact_dispatch_totals(self):
        self.physical_fixture()
        self.physical_reports[1]["saved_application_cache"]["persistent"][
            "lookups"
        ] += 1
        self.seal_physical()
        with self.assertRaisesRegex(ValueError, "accepted Native statistics"):
            self.validate()

    def test_unknown_collector_and_physical_evidence_tampering_are_rejected(self):
        self.compiled["collector"] = "arbitrary"
        self.seal()
        with self.assertRaisesRegex(ValueError, "unknown usage collector"):
            self.validate()
        self.compiled.pop("collector")
        self.physical_fixture()
        reference = self.receipt["reference_launch"]
        (self.repo / reference["path_hint"]).write_text("{}")
        with self.assertRaisesRegex(ValueError, "SHA256 differs"):
            self.validate()

    def test_held_out_and_unknown_roles_or_ids_are_never_eligible(self):
        for role in ("held_out", "training", "unknown", "physical-example"):
            with self.subTest(role=role):
                self.case["role"] = role
                self.seal()
                with self.assertRaisesRegex(ValueError, "authorize"):
                    self.validate()
        self.case["role"] = "tuning"
        self.case["role_evidence"]["json_pointer"] = "/held_out/0"
        self.seal()
        with self.assertRaisesRegex(ValueError, "authorize"):
            self.validate()

    def test_eligibility_rejects_a_held_out_alias_even_when_claimed_as_tuning(self):
        self.document["held_out"][0]["public_input"] = self.document["tuning"][0][
            "public_input"
        ]
        embedded = self.embed(self.document)
        self.profile["eligibility_documents"] = [embedded]
        self.case["role_evidence"]["document_sha256"] = embedded["sha256"]
        self.receipt["identity"]["workload_sha256"] = embedded["sha256"]
        self.seal()
        with self.assertRaisesRegex(ValueError, "held-out"):
            self.validate()

    def test_raw_source_and_canonical_input_hashes_have_distinct_authority(self):
        self.case["public_input_source_sha256"] = self.case["input_sha256"]
        self.seal()
        with self.assertRaisesRegex(ValueError, "mismatched public input"):
            self.validate()

    def test_a_held_out_case_is_rejected_even_when_not_selected(self):
        forbidden = copy.deepcopy(self.case)
        forbidden.update(case_id="final", role="held_out")
        forbidden["role_evidence"]["json_pointer"] = "/held_out/0"
        self.profile["cases"].append(forbidden)
        self.seal()
        with self.assertRaisesRegex(ValueError, "authorize"):
            self.validate()

    def test_unknown_selected_case_and_omitted_dispatch_are_rejected(self):
        self.keys["eligible_case_ids"] = ["unknown"]
        self.seal()
        with self.assertRaisesRegex(ValueError, "unknown case"):
            self.validate()
        self.keys["eligible_case_ids"] = ["tune"]
        self.case["input_dispatch_count"] = 2
        self.seal()
        with self.assertRaisesRegex(ValueError, "omitted an input dispatch"):
            self.validate()

    def test_dispatch_frequency_and_accepted_statistics_are_both_checked(self):
        self.case["dispatches"][0]["records"][0]["backing_hits"] = 3
        self.seal()
        with self.assertRaisesRegex(ValueError, "frequencies do not reconcile"):
            self.validate()
        self.case["dispatches"][0]["persistent"].update(
            route_hits=3, lookups=8, intermediate_hits=5
        )
        self.seal()
        with self.assertRaisesRegex(ValueError, "accepted Native statistics"):
            self.validate()

    def test_dispatch_ordinals_roots_and_owner_masks_are_checked(self):
        dispatch = self.case["dispatches"][0]
        dispatch["ordinal"] = 1
        self.seal()
        with self.assertRaisesRegex(ValueError, "nonconsecutive"):
            self.validate()
        dispatch["ordinal"] = 0
        dispatch["completed_roots"] = 0
        self.seal()
        with self.assertRaisesRegex(ValueError, "roots are incomplete"):
            self.validate()
        dispatch["completed_roots"] = 1
        self.apply["owner_sector"][0] = False
        self.seal()
        with self.assertRaisesRegex(ValueError, "owner differs"):
            self.validate()

    def test_counter_overflow_and_boolean_counts_are_not_accepted(self):
        dispatch = self.case["dispatches"][0]
        dispatch["persistent"]["lookups"] = True
        self.seal()
        with self.assertRaisesRegex(ValueError, "persistent usage counter"):
            self.validate()
        dispatch["persistent"]["lookups"] = 7
        dispatch["records"][0]["backing_hits"] = (1 << 64) - 1
        self.seal()
        with self.assertRaisesRegex(ValueError, "overflow"):
            self.validate()

    def test_selected_keys_need_positive_eligible_frequency_and_are_unique(self):
        self.keys["keys"] = [self.route, self.route]
        self.seal()
        with self.assertRaisesRegex(ValueError, "duplicated"):
            self.validate()
        self.keys["keys"][1] = {"kind": "route", "powers": [2] + [1] * 14}
        self.seal()
        with self.assertRaisesRegex(ValueError, "positive eligible frequency"):
            self.validate()

    def test_observer_and_receipt_fail_closed(self):
        for value in (False, 1):
            self.receipt["cache_hit_diagnostic"]["stream_complete"] = value
            self.seal()
            with (
                self.subTest(value=value),
                self.assertRaisesRegex(ValueError, "lossless trace"),
            ):
                self.validate()

    def test_uncached_or_uninstrumented_receipts_cannot_supply_hit_statistics(self):
        self.receipt["variant"] = "uncached"
        self.seal()
        with self.assertRaisesRegex(ValueError, "completed successful accepted case"):
            self.validate()
        self.receipt["variant"] = "cached"
        self.receipt["identity"]["cache_hit_diagnostic"] = False
        self.seal()
        with self.assertRaisesRegex(ValueError, "completed successful accepted case"):
            self.validate()

    def test_actual_build_stamps_and_source_hashes_are_bound(self):
        self.compiled["main_revision"] = "9" * 40
        self.seal()
        with self.assertRaisesRegex(ValueError, "compiled artifact proof"):
            self.validate()

    def test_measurement_artifact_requires_the_actual_attestation_status(self):
        self.artifacts["status"] = "PASS"
        self.compiled["collector_artifacts"] = self.hint(
            self.save("artifacts.json", self.artifacts)
        )
        self.seal()
        with self.assertRaisesRegex(ValueError, "compiled artifact proof"):
            self.validate()

    def test_native_exporter_artifact_path_cohort_and_elf_are_authenticated(self):
        original = self.raw["collector_artifacts"]
        self.raw["collector_artifacts"] = dict(
            original, path="provenance/light/missing-native-artifact.json"
        )
        self.seal()
        with self.assertRaisesRegex(ValueError, "regular repository file"):
            self.validate()
        artifact = cache_usage.source_json(self.repo, original)
        artifact["binary"]["sha256"] = "9" * 64
        self.raw["collector_artifacts"] = self.save("native-artifact.json", artifact)
        self.seal()
        with self.assertRaisesRegex(ValueError, "cohort or ELF"):
            self.validate()

    def test_native_exporter_cohort_cannot_differ_from_its_artifact(self):
        self.raw["compiled_cohort"] = copy.deepcopy(self.raw["compiled_cohort"])
        self.raw["compiled_cohort"]["main_revision"] = "9" * 40
        self.seal()
        with self.assertRaisesRegex(ValueError, "cohort or ELF"):
            self.validate()

    def test_native_exporter_top_stamps_are_checked(self):
        artifact = cache_usage.source_json(self.repo, self.raw["collector_artifacts"])
        artifact["stamps"][cache_usage.COHORT_FIELDS["kernel_revision"]] = "9" * 40
        self.raw["collector_artifacts"] = self.save("native-artifact.json", artifact)
        self.seal()
        with self.assertRaisesRegex(ValueError, "cohort or ELF"):
            self.validate()

    def test_original_root_loop_and_application_proofs_are_joined(self):
        refs = self.compiled["data_manifests"]
        root = cache_usage.source_json(
            self.repo,
            {"path": refs["root"]["path_hint"], "sha256": refs["root"]["sha256"]},
        )
        root["loop_packs"][0]["manifest_sha256"] = "9" * 64
        reference = self.save("data/root.json", root)
        refs["root"] = self.hint(reference)
        self.profile["data"]["root_manifest_sha256"] = reference["sha256"]
        self.receipt["identity"]["data_manifest_sha256"] = reference["sha256"]
        self.seal()
        with self.assertRaisesRegex(ValueError, "original root does not authenticate"):
            self.validate()

    def test_original_loop_body_must_exist(self):
        reference = self.compiled["data_manifests"]["loop"]
        (self.repo / reference["path_hint"]).unlink()
        with self.assertRaisesRegex(ValueError, "regular repository file"):
            self.validate()

    def test_profile_loop_sha_must_match_its_archived_body(self):
        self.profile["data"]["loop_manifest_sha256"] = "9" * 64
        self.seal()
        with self.assertRaisesRegex(ValueError, "usage data proof SHA differs"):
            self.validate()

    def test_authenticated_loop_application_inventory_must_match_the_source(self):
        references = self.compiled["data_manifests"]
        original_loop = cache_usage.source_json(
            self.repo,
            {
                "path": references["loop"]["path_hint"],
                "sha256": references["loop"]["sha256"],
            },
        )
        for field, value in (("bytes", 99999), ("sha256", "9" * 64)):
            with self.subTest(field=field):
                loop = copy.deepcopy(original_loop)
                loop["files"]["ibps/application.json"][field] = value
                loop_reference = self.save("data/loop.json", loop)
                root = cache_usage.source_json(
                    self.repo,
                    {
                        "path": references["root"]["path_hint"],
                        "sha256": references["root"]["sha256"],
                    },
                )
                root["loop_packs"][0]["manifest_sha256"] = loop_reference["sha256"]
                root_reference = self.save("data/root.json", root)
                references["loop"] = self.hint(loop_reference)
                references["root"] = self.hint(root_reference)
                self.profile["data"]["loop_manifest_sha256"] = loop_reference["sha256"]
                self.profile["data"]["root_manifest_sha256"] = root_reference["sha256"]
                self.receipt["identity"]["data_manifest_sha256"] = root_reference[
                    "sha256"
                ]
                self.seal()
                with self.assertRaisesRegex(
                    ValueError, "original loop does not authenticate"
                ):
                    self.validate()

    def test_accepted_case_cannot_use_a_different_data_root(self):
        self.receipt["identity"]["data_manifest_sha256"] = "9" * 64
        self.seal()
        with self.assertRaisesRegex(
            ValueError, "usage case input/data/collector/binding differs"
        ):
            self.validate()

    def test_native_freeze_authenticates_additional_documentation(self):
        artifact = cache_usage.source_json(self.repo, self.raw["collector_artifacts"])
        freeze = cache_usage.source_json(
            self.repo,
            {name: artifact["source_freeze"][name] for name in ("path", "sha256")},
        )
        documentation = self.repo / freeze["files"]["PRODUCER.typ"]["path"]
        documentation.write_bytes(b"changed archived documentation\n")
        with self.assertRaisesRegex(ValueError, "source proof SHA256 differs"):
            self.validate()

    def test_native_strict_reimport_counts_and_source_snapshot_are_bound(self):
        self.raw["complete_records"] = True
        self.seal()
        with self.assertRaisesRegex(ValueError, "counts differ"):
            self.validate()
        self.raw["complete_records"] = 2
        self.raw["source_cache_native_index_identity"] = {}
        self.seal()
        with self.assertRaisesRegex(ValueError, "cache/source/proofs"):
            self.validate()

    def test_native_receipt_cannot_reference_metadata_or_weaken_strict_flags(self):
        self.raw["metadata_sha256"] = "a" * 64
        self.seal()
        with self.assertRaisesRegex(ValueError, "metadata hash cycle"):
            self.validate()
        del self.raw["metadata_sha256"]
        self.raw["source_unchanged"] = 1
        self.seal()
        with self.assertRaisesRegex(ValueError, "incomplete or not source-bound"):
            self.validate()

    def test_native_identity_comparison_does_not_coerce_booleans_into_bytes(self):
        self.raw["cache_identity"] = copy.deepcopy(self.identity)
        self.raw["cache_identity"]["compressed_blake3"][0] = False
        self.seal()
        with self.assertRaisesRegex(ValueError, "cache/source/proofs"):
            self.validate()

    def test_portable_provenance_refuses_escape_symlink_and_changed_bytes(self):
        reference = self.metadata["selection"]["keys"]
        for name in (
            "../outside.json",
            "/absolute.json",
            "provenance/../outside.json",
            "provenance\\outside.json",
        ):
            with self.subTest(path=name), self.assertRaises(ValueError):
                cache_usage.source_file(self.repo, dict(reference, path=name))
        original = self.repo / reference["path"]
        alias = original.parent / "alias"
        alias.symlink_to(original.parent, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            cache_usage.source_file(
                self.repo, dict(reference, path="provenance/light/alias/keys.json")
            )
        original.write_text("changed")
        with self.assertRaisesRegex(ValueError, "SHA256 differs"):
            self.validate()

    def test_usage_metadata_cannot_mix_in_legacy_completion_or_coverage(self):
        for change in (
            {"coverage_claim": True},
            {"preparation_report": {"status": "complete"}},
        ):
            data.write_json(self.root / "cache.json", dict(self.metadata, **change))
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.validate()

    def test_duplicate_metadata_keys_are_rejected_before_admission(self):
        raw = json.dumps(self.metadata)
        (self.root / "cache.json").write_text('{"schema":"duplicate",' + raw[1:])
        with self.assertRaisesRegex(ValueError, "duplicate source proof JSON key"):
            self.validate()


if __name__ == "__main__":
    unittest.main()
