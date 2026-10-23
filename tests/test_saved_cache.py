import copy
import gzip
import hashlib
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import data
import saved_cache


class SavedCacheAdmissionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="vakint-saved-cache-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "ibps").mkdir()
        (self.root / "ibps/application.json").write_text(
            '{"terminal_maps":"fixture"}\n'
        )
        (self.root / "cache").mkdir()
        # Framing-only fixture. Native coefficient/codec validation is a RustRed gate.
        native = b"opaque fixture, not a native reduction"
        self.decoded = (
            saved_cache.MAGIC + struct.pack("<Q", len(native)) + bytes(32) + native
        )
        self.path = self.root / "cache/prepared.rrcache.gz"
        self.path.write_bytes(gzip.compress(self.decoded, mtime=0))
        self.identity = {
            "compressed_bytes": self.path.stat().st_size,
            "compressed_blake3": [0] * 32,
            "decoded_bytes": len(self.decoded),
            "decoded_blake3": [0] * 32,
        }
        self.decoded_hash = hashlib.sha256(self.decoded).hexdigest()
        self.manifest = {
            "loop_count": 5,
            "dimension": "4-2*epsilon",
            "normalization": "FMFTandMATAD",
            "families": [{"fingerprint": "fixture-family", "denominators": [{}] * 15}],
            "masters": [{"family_sha256": "0" * 64, "powers": [1] * 15}],
            "files": {"cache/prepared.rrcache.gz": data.file_record(self.path)},
        }
        self.manifest["cache"] = {
            "available": True,
            "path": "cache/prepared.rrcache.gz",
            "metadata": "cache.json",
            "format": saved_cache.FORMAT,
            "identity": self.identity,
            "decoded_sha256": self.decoded_hash,
            "binding": {
                "artifact_digest": saved_cache.semantic_digest(
                    self.root, self.manifest
                ),
                "family_fingerprint": "fixture-family",
                "physical_arity": 15,
                "layer": "saved-application-route-apply-v1",
            },
        }
        self.workload = {
            "schema": "vakint.five-loop-cache-workload.v1",
            "data_manifest_sha256": "0" * 64,
            "source_census_sha256": "1" * 64,
            "training": [
                {"id": "selected", "powers": [1] * 15, "rationale": "selected control"}
            ],
            "tuning": [],
            "held_out": [
                {
                    "id": f"held-{i}",
                    "powers": [i] + [1] * 14,
                    "rationale": "unselected dot change",
                }
                for i in range(2, 14)
            ],
        }
        data.write_json(self.root / "cache/workload.json", self.workload)
        self.metadata = {
            "schema": "vakint.external-data.saved-cache.v1",
            "strict": True,
            "workload": {
                "path": "cache/workload.json",
                "sha256": data.digest(self.root / "cache/workload.json"),
            },
            "preparation_report": {
                "status": "complete",
                "completed_roots": 1,
                "total_roots": 1,
                "failure": None,
                "native_profile": {
                    "strict": True,
                    "unresolved_policy": "reject",
                    "entry_coverage": "advisory",
                    "required_root_postcondition": "complete-native-declared-terminals",
                    "roots": [
                        {
                            "namespace": 0,
                            "powers": [1] * 15,
                            "coverage_admitted": True,
                        }
                    ],
                },
            },
            "final_build_elapsed_seconds": 10,
        }
        data.write_json(self.root / "cache.json", self.metadata)

    def test_complete_finite_workload_passes_source_admission(self):
        saved_cache.validate(self.root, self.manifest)

    def test_complete_root_outside_recorded_coverage_passes_source_admission(self):
        profile = self.metadata["preparation_report"]["native_profile"]
        profile["roots"][0]["coverage_admitted"] = False
        data.write_json(self.root / "cache.json", self.metadata)
        saved_cache.validate(self.root, self.manifest)

    def test_native_profile_requires_explicit_strict_completion_policy(self):
        for field in (
            "strict",
            "unresolved_policy",
            "entry_coverage",
            "required_root_postcondition",
            "roots",
        ):
            metadata = copy.deepcopy(self.metadata)
            del metadata["preparation_report"]["native_profile"][field]
            data.write_json(self.root / "cache.json", metadata)
            with (
                self.subTest(missing=field),
                self.assertRaisesRegex(ValueError, "native profile"),
            ):
                saved_cache.validate(self.root, self.manifest)
        for field, value in (
            ("strict", False),
            ("strict", 1),
            ("unresolved_policy", "preserve"),
            ("unresolved_policy", "unknown"),
            ("entry_coverage", "unknown"),
            ("required_root_postcondition", "unknown"),
        ):
            metadata = copy.deepcopy(self.metadata)
            metadata["preparation_report"]["native_profile"][field] = value
            data.write_json(self.root / "cache.json", metadata)
            with (
                self.subTest(field=field, value=value),
                self.assertRaisesRegex(ValueError, "strict completion policy"),
            ):
                saved_cache.validate(self.root, self.manifest)

    def test_native_profile_rejects_wrong_roots_and_noncanonical_values(self):
        for changes in (
            {"namespace": 1},
            {"namespace": False},
            {"powers": [2] + [1] * 14},
            {"powers": [1] * 14},
            {"powers": [True] + [1] * 14},
            {"powers": [1 << 63] + [1] * 14},
            {"powers": [-(1 << 63) - 1] + [1] * 14},
            {"coverage_admitted": 0},
            {"coverage_admitted": "false"},
            {"state": "unknown"},
        ):
            metadata = copy.deepcopy(self.metadata)
            metadata["preparation_report"]["native_profile"]["roots"][0].update(changes)
            data.write_json(self.root / "cache.json", metadata)
            with (
                self.subTest(changes=changes),
                self.assertRaisesRegex(ValueError, "native profile root"),
            ):
                saved_cache.validate(self.root, self.manifest)

    def test_native_profile_roots_follow_canonical_order_of_selected_powers(self):
        powers = [-1] + [1] * 14
        self.workload["training"].append(
            {"id": "numerator", "powers": powers, "rationale": "signed power control"}
        )
        data.write_json(self.root / "cache/workload.json", self.workload)
        self.metadata["workload"]["sha256"] = data.digest(
            self.root / "cache/workload.json"
        )
        report = self.metadata["preparation_report"]
        report["completed_roots"] = report["total_roots"] = 2
        roots = report["native_profile"]["roots"]
        roots.insert(0, {"namespace": 0, "powers": powers, "coverage_admitted": False})
        data.write_json(self.root / "cache.json", self.metadata)
        saved_cache.validate(self.root, self.manifest)
        for wrong_roots in (roots[::-1], roots[:1], roots + roots[:1]):
            metadata = copy.deepcopy(self.metadata)
            metadata["preparation_report"]["native_profile"]["roots"] = wrong_roots
            data.write_json(self.root / "cache.json", metadata)
            with (
                self.subTest(roots=wrong_roots),
                self.assertRaisesRegex(ValueError, "roots differ"),
            ):
                saved_cache.validate(self.root, self.manifest)

    def test_digest_binds_exact_application_catalogue_and_normalization_only(self):
        expected = saved_cache.semantic_digest(self.root, self.manifest)
        presentation = copy.deepcopy(self.manifest)
        presentation.update(version="v999.0.0", cache={"available": False})
        presentation["masters"][0].update(name="renamed", coefficients=[])
        self.assertEqual(saved_cache.semantic_digest(self.root, presentation), expected)
        for field in ("dimension", "normalization"):
            changed = copy.deepcopy(self.manifest)
            changed[field] = "different"
            self.assertNotEqual(
                saved_cache.semantic_digest(self.root, changed), expected
            )
        changed = copy.deepcopy(self.manifest)
        changed["masters"][0]["powers"][0] = -1
        self.assertNotEqual(saved_cache.semantic_digest(self.root, changed), expected)
        (self.root / "ibps/application.json").write_text(
            '{"terminal_maps":"changed"}\n'
        )
        self.assertNotEqual(
            saved_cache.semantic_digest(self.root, self.manifest), expected
        )
        with self.assertRaisesRegex(ValueError, "binding differs"):
            saved_cache.validate(self.root, self.manifest)

    def test_single_member_crc_bounds_and_decoded_identity_are_required(self):
        original = self.path.read_bytes()
        for suffix in (b"trailing", gzip.compress(b"", mtime=0)):
            self.path.write_bytes(original + suffix)
            identity = dict(self.identity, compressed_bytes=self.path.stat().st_size)
            with self.assertRaisesRegex(ValueError, "trailing"):
                saved_cache.check_gzip(self.path, identity, self.decoded_hash)
        corrupted = bytearray(original)
        corrupted[-8] ^= 1
        self.path.write_bytes(corrupted)
        with self.assertRaisesRegex(ValueError, "CRC"):
            saved_cache.check_gzip(self.path, self.identity, self.decoded_hash)
        self.path.write_bytes(original)
        for identity in (
            dict(self.identity, decoded_bytes=len(self.decoded) - 1),
            dict(self.identity, decoded_bytes=saved_cache.MAX_DECODED + 1),
            dict(self.identity, compressed_bytes=saved_cache.MAX_COMPRESSED + 1),
            dict(self.identity, compressed_blake3=[True] * 32),
        ):
            with self.assertRaises(ValueError):
                saved_cache.check_gzip(self.path, identity, self.decoded_hash)
        with self.assertRaises(ValueError):
            saved_cache.check_gzip(self.path, self.identity, "0" * 64)

    def test_incomplete_partial_overtime_and_overlapping_workloads_are_rejected(self):
        for field, value in (
            ("completed_roots", 0),
            ("completed_roots", True),
            ("status", "cancelled"),
            ("failure", "incomplete"),
            ("native_profile", {"strict": False}),
        ):
            metadata = copy.deepcopy(self.metadata)
            metadata["preparation_report"][field] = value
            data.write_json(self.root / "cache.json", metadata)
            with self.subTest(field=field), self.assertRaises(ValueError):
                saved_cache.validate(self.root, self.manifest)
        for elapsed in (36001, -1, float("nan"), True):
            metadata = dict(self.metadata, final_build_elapsed_seconds=elapsed)
            data.write_json(self.root / "cache.json", metadata)
            with self.subTest(elapsed=elapsed), self.assertRaises(ValueError):
                saved_cache.validate(self.root, self.manifest)
        self.workload["held_out"][0]["powers"] = [1] * 15
        data.write_json(self.root / "cache/workload.json", self.workload)
        self.metadata["workload"]["sha256"] = data.digest(
            self.root / "cache/workload.json"
        )
        data.write_json(self.root / "cache.json", self.metadata)
        with self.assertRaisesRegex(ValueError, "overlap"):
            saved_cache.validate(self.root, self.manifest)

    def test_larger_file_requires_authenticated_measured_twenty_percent_gain(self):
        comparison = self.root / "cache/comparison.json"
        data.write_json(comparison, {"fixture": "measured timing evidence lives here"})
        with patch.object(saved_cache, "TARGET_COMPRESSED", 1):
            with self.assertRaisesRegex(ValueError, "performance exception"):
                saved_cache.validate(self.root, self.manifest)
            self.metadata["size_exception"] = {
                "metric": "quadratic-median-ibp",
                "baseline_compressed_bytes": 1,
                "comparison": {
                    "path": "cache/comparison.json",
                    "sha256": data.digest(comparison),
                },
                "baseline_seconds": 10,
                "candidate_seconds": 8,
            }
            data.write_json(self.root / "cache.json", self.metadata)
            saved_cache.validate(self.root, self.manifest)
            self.metadata["size_exception"]["candidate_seconds"] = 8.01
            data.write_json(self.root / "cache.json", self.metadata)
            with self.assertRaisesRegex(ValueError, "20 percent"):
                saved_cache.validate(self.root, self.manifest)


if __name__ == "__main__":
    unittest.main()
