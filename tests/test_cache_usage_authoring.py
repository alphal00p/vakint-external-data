"""Synthetic authoring contracts; no Native payload or reduction is evaluated."""

import copy
import gzip
import hashlib
import io
import json
import stat
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import cache_usage
import test_cache_usage


class UsageCandidateAuthoringTests(unittest.TestCase):
    def setUp(self):
        composed = test_cache_usage.ComposedUsageProfileTests(
            "test_distinct_real_collectors_share_counts_without_a_global_elf"
        )
        composed.setUp()
        self.addCleanup(composed.doCleanups)
        self.composed = composed
        self.fixture = composed.f
        self.output = "provenance/authored-candidates"
        self.references = {
            member["id"]: member["profile"] for member in composed.outer["members"]
        }

    def author(self, **overrides):
        arguments = {
            "root": self.fixture.repo,
            "directory": self.fixture.root,
            "manifest": self.fixture.manifest,
            "source": self.fixture.metadata["selection"]["source"],
            "physical_ref": self.references["physical"],
            "tuning_ref": self.references["tuning"],
            "additions": [0, 1],
            "output_relative": self.output,
        }
        arguments.update(overrides)
        return cache_usage.author_candidates(**arguments)

    def reseal_profile(self, member):
        self.references[member] = self.fixture.save(
            "authoring/" + member + ".json", self.composed.children[member]
        )

    def snapshot(self):
        result = {}
        for path in self.fixture.repo.rglob("*"):
            if stat.S_ISREG(path.lstat().st_mode):
                result[str(path.relative_to(self.fixture.repo))] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
        return result

    @staticmethod
    def read_gzip(path):
        return cache_usage.decode_json(gzip.decompress(path.read_bytes()))

    def rejected(self, **overrides):
        before = self.snapshot()
        with self.assertRaises((ValueError, OSError)):
            self.author(**overrides)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.fixture.repo / self.output).exists())

    def test_candidates_pass_the_real_composed_validator_and_preserve_core(self):
        before = self.snapshot()
        report = self.author()
        directory = self.fixture.repo / self.output
        profile_path = directory / "usage-profile.json.gz"
        profile = self.read_gzip(profile_path)
        self.assertEqual(profile["schema"], cache_usage.PROFILE_V2_SCHEMA)
        self.assertEqual(len(profile["members"]), 2)
        expected = [
            {cache_usage.work(self.fixture.route, 15)},
            {
                cache_usage.work(self.fixture.route, 15),
                cache_usage.work(self.fixture.apply, 15),
            },
        ]
        for count, keys_expected in enumerate(expected):
            with self.subTest(additional_keys=count):
                selection = self.read_gzip(
                    directory / f"selected-keys-{count:06d}.json.gz"
                )
                self.assertEqual(
                    selection["schema"], "vakint.cache-record-selection.v1"
                )
                self.assertEqual(
                    selection["usage_profile_sha256"],
                    hashlib.sha256(profile_path.read_bytes()).hexdigest(),
                )
                self.assertEqual(
                    selection["selection"]["max_compressed_bytes"], 95_000_000
                )
                self.assertEqual(
                    {cache_usage.work(row, 15) for row in selection["keys"]},
                    keys_expected,
                )
                frequencies = cache_usage.admitted_profile_frequencies(
                    self.fixture.repo,
                    profile,
                    selection,
                    self.fixture.binding,
                    self.fixture.root,
                    self.fixture.metadata["selection"]["source"],
                    self.fixture.manifest,
                )
                self.assertEqual(
                    frequencies[cache_usage.work(self.fixture.route, 15)], 4
                )
                self.assertEqual(
                    frequencies[cache_usage.work(self.fixture.apply, 15)], 6
                )
        after = self.snapshot()
        self.assertEqual({key: after[key] for key in before}, before)
        self.assertTrue(set(after) - set(before))
        self.assertTrue(
            all(path.startswith(self.output + "/") for path in set(after) - set(before))
        )
        self.assertTrue((directory / "ranking.json.gz").is_file())
        self.assertTrue((directory / "authoring-report.json").is_file())
        ranking = self.read_gzip(directory / "ranking.json.gz")
        self.assertIsNone(ranking["per_key_native_work_avoided"])
        self.assertIsNone(ranking["per_key_compressed_bytes"])
        rows = {cache_usage.work(row["work"], 15): row for row in ranking["rows"]}
        self.assertEqual(
            rows[cache_usage.work(self.fixture.route, 15)]["backing_hits"], 4
        )
        self.assertEqual(
            rows[cache_usage.work(self.fixture.apply, 15)]["backing_hits"], 6
        )
        self.assertTrue(rows[cache_usage.work(self.fixture.route, 15)]["core"])
        self.assertFalse(rows[cache_usage.work(self.fixture.apply, 15)]["core"])
        for candidate in report["candidates"]:
            self.assertIsNone(candidate["compressed_cache_bytes"])
            self.assertIsNone(candidate["decoded_cache_bytes"])
            self.assertFalse(candidate["native_export_accepted"])

    def test_core_only_never_adds_an_intermediate_with_a_higher_hit_count(self):
        self.author(additions=[0])
        directory = self.fixture.repo / self.output
        files = sorted(directory.glob("selected-keys-*.json.gz"))
        self.assertEqual(
            [path.name for path in files], ["selected-keys-000000.json.gz"]
        )
        self.assertEqual(self.read_gzip(files[0])["keys"], [self.fixture.route])

    def test_candidate_prefixes_prioritize_reuse_before_hits_with_stable_ties(self):
        twice, many_hits, first_tie, second_tie = [
            {"kind": "route", "powers": [power] + [1] * 14} for power in (2, 3, 4, 5)
        ]
        case = self.composed.children["tuning"]["cases"][0]
        first = case["dispatches"][0]
        first["records"].extend(
            {"work": work, "backing_hits": hits}
            for work, hits in (
                (twice, 1),
                (many_hits, 100),
                (second_tie, 5),
                (first_tie, 5),
            )
        )
        first["persistent"] = {
            "lookups": 118,
            "misses": 2,
            "route_hits": 113,
            "apply_hits": 3,
            "requested_root_hits": 1,
            "intermediate_hits": 115,
        }
        case["input_dispatch_count"] = 2
        case["dispatches"].append(
            {
                "ordinal": 1,
                "requested_roots": 1,
                "completed_roots": 1,
                "collected_roots": [self.fixture.route],
                "persistent": {
                    "lookups": 2,
                    "misses": 1,
                    "route_hits": 1,
                    "apply_hits": 0,
                    "requested_root_hits": 0,
                    "intermediate_hits": 1,
                },
                "records": [{"work": twice, "backing_hits": 1}],
            }
        )
        totals = {
            "lookups": 120,
            "misses": 3,
            "route_hits": 114,
            "apply_hits": 3,
            "requested_root_hits": 1,
            "intermediate_hits": 116,
        }
        self.composed.edit_receipt(
            "tuning",
            lambda receipt: receipt["cache_statistics"].update(persistent=totals),
        )
        self.reseal_profile("tuning")
        self.author(additions=[0, 1, 2, 3, 4, 5])
        expected_extra_order = [
            self.fixture.apply,
            twice,
            many_hits,
            first_tie,
            second_tie,
        ]
        directory = self.fixture.repo / self.output
        profile = self.read_gzip(directory / "usage-profile.json.gz")
        for count in range(6):
            selection = self.read_gzip(directory / f"selected-keys-{count:06d}.json.gz")
            expected = [self.fixture.route, *expected_extra_order[:count]]
            self.assertEqual(
                {cache_usage.work(row, 15) for row in selection["keys"]},
                {cache_usage.work(row, 15) for row in expected},
            )
            counts = cache_usage.admitted_profile_frequencies(
                self.fixture.repo,
                profile,
                selection,
                self.fixture.binding,
                self.fixture.root,
                self.fixture.metadata["selection"]["source"],
                self.fixture.manifest,
            )
            self.assertEqual(counts[cache_usage.work(many_hits, 15)], 100)

    def test_profile_and_candidate_bytes_are_reproducible_in_distinct_outputs(self):
        self.author()
        second = "provenance/authored-candidates-again"
        self.author(output_relative=second)
        first = self.fixture.repo / self.output
        for name in (
            "usage-profile.json.gz",
            "selected-keys-000000.json.gz",
            "selected-keys-000001.json.gz",
            "ranking.json.gz",
        ):
            self.assertEqual(
                (first / name).read_bytes(),
                (self.fixture.repo / second / name).read_bytes(),
            )

    def test_swapping_collectors_is_rejected_before_any_output(self):
        self.rejected(
            physical_ref=self.references["tuning"],
            tuning_ref=self.references["physical"],
        )

    def test_multiple_cases_cannot_expand_the_single_tuning_authority(self):
        self.composed.children["tuning"]["cases"].append(
            copy.deepcopy(self.composed.children["tuning"]["cases"][0])
        )
        self.reseal_profile("tuning")
        self.rejected()

    def test_nested_or_unknown_profile_schema_is_rejected(self):
        profile = self.composed.children["physical"]
        for schema in (cache_usage.PROFILE_V2_SCHEMA, "unknown-profile"):
            with self.subTest(schema=schema):
                profile["schema"] = schema
                self.reseal_profile("physical")
                self.rejected()

    def test_unaccepted_actual_receipt_is_rejected(self):
        self.composed.edit_receipt(
            "tuning", lambda receipt: receipt.update(success=False)
        )
        self.reseal_profile("tuning")
        self.rejected()

    def test_sampled_observer_cannot_author_a_candidate(self):
        self.composed.children["physical"]["cases"][0]["interval_ns"] = 1
        self.reseal_profile("physical")
        self.rejected()

    def test_full_receipt_statistics_are_required_in_addition_to_profile_counts(self):
        self.composed.children["tuning"]["cases"][0]["dispatches"][0]["persistent"][
            "apply_hits"
        ] += 1
        self.reseal_profile("tuning")
        self.rejected()

    def test_cross_member_held_out_alias_is_rejected(self):
        authority = copy.deepcopy(self.fixture.document)
        authority["held_out"] = [{"id": "alias", "public_input": "vacuum( 1 )"}]
        self.composed.children["physical"]["eligibility_documents"].append(
            self.fixture.embed(authority)
        )
        self.reseal_profile("physical")
        self.rejected()

    def test_cohort_changes_are_not_authoring_shortcuts(self):
        self.composed.children["tuning"]["compiled_cohort"]["kernel_revision"] = (
            "9" * 40
        )
        self.reseal_profile("tuning")
        self.rejected()

    def test_changed_active_master_catalogue_is_rejected(self):
        manifest = copy.deepcopy(self.fixture.manifest)
        manifest["masters"][0]["powers"][0] += 1
        self.rejected(manifest=manifest)

    def test_existing_cache_binding_cannot_disagree_with_authenticated_source(self):
        manifest = copy.deepcopy(self.fixture.manifest)
        manifest["cache"]["binding"]["artifact_digest"][0] ^= 1
        self.rejected(manifest=manifest)

    def test_source_without_an_active_cache_can_still_author_candidates(self):
        manifest = copy.deepcopy(self.fixture.manifest)
        del manifest["cache"]
        self.author(manifest=manifest, additions=[0])
        self.assertTrue(
            (self.fixture.repo / self.output / "selected-keys-000000.json.gz").is_file()
        )

    def test_missing_input_and_changed_reference_hashes_fail_without_output(self):
        self.rejected(
            physical_ref={"path": "provenance/absent.json", "sha256": "0" * 64}
        )
        self.rejected(physical_ref=dict(self.references["physical"], sha256="0" * 64))

    def test_empty_negative_boolean_and_duplicate_candidate_counts_are_rejected(self):
        for additions in ([], [-1], [True], [0, 0], [0, 1.0]):
            with self.subTest(additions=additions):
                self.rejected(additions=additions)

    def test_unsafe_output_paths_do_not_write_outside_provenance(self):
        for destination in (
            "../escape",
            str(self.fixture.repo / "absolute-invalid"),
            "provenance/../escape",
            "provenance\\escape",
            "5L/cache/authoring",
        ):
            with self.subTest(destination=destination):
                self.rejected(output_relative=destination)

    def test_symlinked_input_and_output_parents_are_rejected(self):
        source = self.fixture.repo / self.references["physical"]["path"]
        alias = source.parent / "profile-alias.json"
        alias.symlink_to(source)
        self.rejected(
            physical_ref={
                "path": str(alias.relative_to(self.fixture.repo)),
                "sha256": self.references["physical"]["sha256"],
            }
        )
        output_alias = self.fixture.repo / "provenance/output-alias"
        output_alias.symlink_to(source.parent, target_is_directory=True)
        self.rejected(output_relative="provenance/output-alias/never-created")

    def test_existing_output_directory_is_never_overwritten(self):
        destination = self.fixture.repo / self.output
        destination.mkdir()
        sentinel = destination / "sentinel"
        sentinel.write_bytes(b"preserve existing results\n")
        before = self.snapshot()
        with self.assertRaises((ValueError, OSError)):
            self.author()
        self.assertEqual(self.snapshot(), before)

    def test_failed_staging_write_leaves_no_partial_directory(self):
        original = Path.write_bytes
        staging_writes = []

        def fail_second_write(path, value):
            if path.parent.name.startswith(".light-authoring-"):
                staging_writes.append(path.name)
                if len(staging_writes) == 2:
                    raise OSError("injected staging write failure")
            return original(path, value)

        with patch.object(Path, "write_bytes", fail_second_write):
            self.rejected()
        self.assertEqual(len(staging_writes), 2)
        self.assertEqual(
            list((self.fixture.repo / "provenance").glob(".light-authoring-*")), []
        )

    def test_failed_publication_cleans_staging_and_preserves_source(self):
        with patch.object(
            cache_usage.os, "rename", side_effect=OSError("injected rename failure")
        ):
            self.rejected()
        self.assertEqual(
            list((self.fixture.repo / "provenance").glob(".light-authoring-*")), []
        )

    def test_concurrent_output_creation_is_preserved(self):
        destination = self.fixture.repo / self.output
        original = Path.mkdir
        created = []

        def create_before_reservation(path, *args, **kwargs):
            if path == destination and not created:
                original(path)
                (path / "other-owner").write_bytes(b"independent results\n")
                created.append(path.stat())
            return original(path, *args, **kwargs)

        before = self.snapshot()
        with (
            patch.object(Path, "mkdir", create_before_reservation),
            self.assertRaises((ValueError, OSError)),
        ):
            self.author()
        self.assertEqual(len(created), 1)
        self.assertEqual(destination.stat().st_ino, created[0].st_ino)
        self.assertEqual(
            (destination / "other-owner").read_bytes(), b"independent results\n"
        )
        after = self.snapshot()
        self.assertEqual({key: after[key] for key in before}, before)
        self.assertEqual(set(after) - set(before), {self.output + "/other-owner"})
        self.assertEqual(
            list((self.fixture.repo / "provenance").glob(".light-authoring-*")), []
        )

    def test_cli_accepts_authenticated_ordinary_loop_manifest(self):
        manifest = self.fixture.root / "manifest.json"
        manifest.write_text(json.dumps(self.fixture.manifest))
        source = self.fixture.save(
            "authoring/source.json", self.fixture.metadata["selection"]["source"]
        )
        arguments = ["author", "--root", str(self.fixture.repo)]
        for name, reference in (
            (
                "loop-manifest",
                {
                    "path": "5L/manifest.json",
                    "sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                },
            ),
            ("source", source),
            ("physical-profile", self.references["physical"]),
            ("tuning-profile", self.references["tuning"]),
        ):
            arguments.extend(
                [
                    f"--{name}",
                    reference["path"],
                    f"--{name}-sha256",
                    reference["sha256"],
                ]
            )
        arguments.extend(["--additional-keys", "0", "--output-dir", self.output])
        with patch("sys.stdout", new_callable=io.StringIO) as output:
            cache_usage.main(arguments)
        report = json.loads(output.getvalue())
        self.assertFalse(report["native_payloads_opened"])
        self.assertEqual(report["core_keys"], 1)
        self.assertTrue(
            (self.fixture.repo / self.output / "authoring-report.json").is_file()
        )


if __name__ == "__main__":
    unittest.main()
