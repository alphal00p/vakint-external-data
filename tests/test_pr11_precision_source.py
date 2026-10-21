"""Adapter controls; actual scientific replay is exercised by source validation."""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import data
import precision_supplement as precision


class Pr11SourceAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle = self.root / "validation/pr11d-20000"
        self.bundle.mkdir(parents=True)
        self.period = {
            "symbol": "PR11dep0",
            "master_basis": "vakint::PR11d",
            "master_id": "L4_adapter_fixture",
            "family_sha256": "1" * 64,
            "ordered_powers": [0, 2, 1, 1, 1, 1, 1, 1, 1, 0],
            "epsilon_power": 0,
            "normalization": "FMFT",
            "unit_mass_squared": "1",
            "error_quality": "rigorous-bound",
            "Minkowski_overall_sign": -1,
            "validated_significant_digits": 20000,
            "stored_significant_digits": 20008,
            "value": "-1." + "2" * 20007,
            "absolute_error_upper_bound": "1e-20010",
        }
        self.payload = {
            "schema": "vakint.pr11d.validated-periods.v1",
            "constants": {"PR11dep0": self.period},
        }
        self.verifier = self.bundle / "verify_bundle.py"
        self.verifier.write_text("# Non-executed adapter test fixture.\n")
        self.verifier_hash = data.digest(self.verifier)
        data.write_json(self.bundle / "provenance-manifest.json", {})
        data.write_json(self.bundle / "proof.json", {})
        self.index = {
            "schema": "vakint.pr11d.portable-proof-index.v1",
            "artifacts": {
                "provenance_manifest": self.descriptor("provenance-manifest.json"),
            },
            "implementations": {"verify_bundle": self.descriptor("verify_bundle.py")},
            "files": {"/original/proof.json": self.descriptor("proof.json")},
        }
        self.reference = {"kind": precision.PR11_SOURCE_KIND}
        self.write_artifacts()
        master = {
            "master_id": self.period["master_id"],
            "family_sha256": self.period["family_sha256"],
            "powers": self.period["ordered_powers"],
            "exact_basis_expression": "vakint::{}::PR11d",
        }
        data.write_json(self.root / "4L/manifest.json", {"masters": [master]})

    def descriptor(self, name):
        path = self.bundle / name
        return {"path": name, "sha256": data.digest(path), "bytes": path.stat().st_size}

    def write_artifacts(self):
        for name, contents, filename in [
            ("payload", self.payload, "periods.json"),
            ("validation", {"accepted": True}, "validation.json"),
        ]:
            data.write_json(self.bundle / filename, contents)
            self.index["artifacts"][name] = self.descriptor(filename)
            self.reference[name] = {
                "path": "validation/pr11d-20000/" + filename,
                "sha256": data.digest(self.bundle / filename),
            }
        data.write_json(self.bundle / "proof-index.json", self.index)
        self.reference["proof_manifest"] = {
            "path": "validation/pr11d-20000/proof-index.json",
            "sha256": data.digest(self.bundle / "proof-index.json"),
        }

    def verification(self):
        return {
            "schema": "vakint.pr11d.portable-bundle-verification.v1",
            "accepted": True,
            "payload_sha256": self.reference["payload"]["sha256"],
            "provenance_manifest_sha256": self.index["artifacts"][
                "provenance_manifest"
            ]["sha256"],
            "validated_significant_digits": 20000,
            "stored_significant_digits": 20008,
            "two_refinement_interval_convolutions_replayed": True,
            "complete_independent_DE_validation": False,
            "AMFlow_20000_digit_comparison_claimed": False,
            "native_or_Mathematica_execution": False,
        }

    def load(self, report=None):
        # The adapter is isolated from mathematical replay. Production cannot
        # admit this fixture: its executable hash differs from the fixed pin.
        with (
            patch.object(precision, "PR11_VERIFIER_SHA256", self.verifier_hash),
            patch.object(
                precision,
                "_verify_pr11_bundle",
                return_value=self.verification() if report is None else report,
            ),
        ):
            return precision._load_pr11_source(self.root, self.reference)

    def test_verified_finite_projection_preserves_center_sign_and_bound(self):
        [row] = self.load()
        self.assertEqual(row["symbol"], "PR11dep0")
        self.assertEqual(row["master_basis"], "vakint::PR11d")
        self.assertEqual(row["epsilon_power"], 0)
        self.assertEqual(row["normalization"], "FMFTandMATAD")
        self.assertEqual(row["significant_digits"], 20000)
        self.assertEqual(row["stored_significant_digits"], 20008)
        self.assertEqual(row["numerical_value"], self.period["value"])
        self.assertEqual(row["validation"]["absolute_error_bound"], "1e-20010")

    def test_self_consistent_untrusted_verifier_is_not_an_admission_root(self):
        with (
            patch.object(precision, "_verify_pr11_bundle") as run,
            self.assertRaisesRegex(ValueError, "not the independently accepted"),
        ):
            precision._load_pr11_source(self.root, self.reference)
        run.assert_not_called()

    def test_changed_artifact_or_verifier_bytes_are_rejected(self):
        for path in [self.bundle / "periods.json", self.verifier]:
            original = path.read_bytes()
            path.write_bytes(original + b" ")
            with (
                self.subTest(path=path),
                self.assertRaisesRegex(ValueError, "checksum or size"),
            ):
                self.load()
            path.write_bytes(original)

    def test_outer_and_indexed_artifacts_must_be_identical(self):
        data.write_json(self.bundle / "other.json", {"accepted": True})
        self.index["artifacts"]["payload"] = self.descriptor("other.json")
        data.write_json(self.bundle / "proof-index.json", self.index)
        self.reference["proof_manifest"]["sha256"] = data.digest(
            self.bundle / "proof-index.json"
        )
        with self.assertRaisesRegex(ValueError, "outer artifact differs"):
            self.load()

    def test_proof_paths_reject_escapes_and_in_root_parent_symlinks(self):
        for path in ["../proof.json", "/absolute/proof.json", "bad\\proof.json"]:
            self.index["files"]["/original/proof.json"]["path"] = path
            self.write_artifacts()
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.load()
        actual = self.bundle / "actual"
        actual.mkdir()
        data.write_json(actual / "proof.json", {})
        (self.bundle / "linked").symlink_to(actual, target_is_directory=True)
        self.index["files"]["/original/proof.json"]["path"] = "linked/proof.json"
        self.write_artifacts()
        with self.assertRaisesRegex(ValueError, "symlinks"):
            self.load()

    def test_verifier_result_cannot_overstate_scope_or_change_payload(self):
        for field, value in [
            ("accepted", False),
            ("payload_sha256", "0" * 64),
            ("two_refinement_interval_convolutions_replayed", False),
            ("validated_significant_digits", 20001),
            ("complete_independent_DE_validation", True),
            ("AMFlow_20000_digit_comparison_claimed", True),
            ("native_or_Mathematica_execution", True),
        ]:
            report = {**self.verification(), field: value}
            with (
                self.subTest(field=field),
                self.assertRaisesRegex(ValueError, "verification result"),
            ):
                self.load(report)

    def test_scope_identity_and_stored_precision_fail_closed(self):
        for field, value in [
            ("epsilon_power", 1),
            ("epsilon_power", False),
            ("normalization", "native_raw"),
            ("Minkowski_overall_sign", 1),
            ("master_id", "invented"),
            ("family_sha256", "0" * 64),
            ("ordered_powers", [1] * 10),
            ("value", "NaN"),
            ("value", "0"),
            ("value", "1.234"),
            ("stored_significant_digits", 20009),
        ]:
            original = self.period[field]
            self.period[field] = value
            self.write_artifacts()
            with (
                self.subTest(field=field, value=str(value)[:40]),
                self.assertRaises(ValueError),
            ):
                self.load()
            self.period[field] = original

    def test_duplicate_index_keys_and_invalid_descriptors_are_rejected(self):
        reference = copy.deepcopy(self.reference)
        reference["payload"]["encoding"] = "gzip"
        with self.assertRaisesRegex(ValueError, "plaintext artifact descriptor"):
            precision._load_pr11_source(self.root, reference)
        index = self.bundle / "proof-index.json"
        content = index.read_text()
        index.write_text(
            content.replace('"schema":', '"schema": "duplicate", "schema":', 1)
        )
        self.reference["proof_manifest"]["sha256"] = data.digest(index)
        with self.assertRaisesRegex(ValueError, "duplicate PR11 JSON"):
            self.load()

    def test_authenticated_verifier_is_executed_from_an_isolated_private_copy(self):
        observed = []

        def run(command, **options):
            script = Path(command[3])
            self.assertEqual(script.read_bytes(), self.verifier.read_bytes())
            self.assertEqual(command[:3], [sys.executable, "-I", "-B"])
            self.assertEqual(
                command[4:], [str(self.bundle), "--index", "proof-index.json"]
            )
            self.assertNotEqual(script, self.verifier)
            self.assertTrue(options["check"])
            observed.append(script)
            return type("Result", (), {"stdout": json.dumps(self.verification())})()

        with patch.object(precision.subprocess, "run", side_effect=run):
            result = precision._verify_pr11_bundle(
                self.bundle, "proof-index.json", self.verifier.read_bytes()
            )
        self.assertEqual(result, self.verification())
        self.assertFalse(observed[0].exists())


if __name__ == "__main__":
    unittest.main()
