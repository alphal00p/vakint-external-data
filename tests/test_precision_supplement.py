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


class PrecisionSupplementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.identity = "L4_fixture"
        self.master = {
            "master_id": self.identity,
            "loop_count": 4,
            "exact_basis_expression": "vakint::{}::PR4",
            "files": {},
        }
        entry = {
            "loop_count": 4,
            "exact_basis_expression": "vakint::{}::PR4",
            "coefficients": [],
            "sources": {},
            "files": {},
            "previous_files": {},
        }
        for power, value in [(0, "1.2500000"), (1, "3.5000000")]:
            entry["coefficients"].append(
                {
                    "epsilon_power": power,
                    "symbolic": False,
                    "numerical": True,
                    "significant_digits": 4,
                    "stored_significant_digits": 8,
                    "absolute_error": "1e-8",
                    "error_quality": "bounded",
                }
            )
            entry["sources"][str(power)] = {
                "symbol": "fixture",
                "numerical_sha256": precision.text_digest(value),
            }
        for name in ["numerical.json", "symbolic.json"]:
            relative = f"masters/P6/{name}"
            contents = json.dumps([[-1, "2"], [0, "1.25"], [1, "3.5"]]) + "\n"
            entry["previous_files"][name] = {
                "path": relative,
                "contents": contents,
                "sha256": precision.text_digest(contents),
            }
            data.write_json(
                self.root / "4L" / relative,
                [[-1, "2"], [0, "1.2500000"], [1, "3.5000000"]],
            )
            record = {
                "path": relative,
                "sha256": data.digest(self.root / "4L" / relative),
            }
            entry["files"][name] = record
            self.master["files"][name] = record.copy()
        self.update = {
            "schema": precision.SCHEMA,
            "normalization": "FMFTandMATAD",
            "masters": {self.identity: entry},
        }
        data.write_json(self.root / "4L" / precision.LOOP_RECEIPT, self.update)

    def test_preserves_explicit_bounds_and_accepts_only_preserved_bindings(self):
        rows = precision.coefficients(self.update, {self.identity: self.master})[
            self.identity
        ]
        self.assertEqual(rows[0]["absolute_error"], "1e-8")
        self.assertEqual(rows[0]["error_quality"], "bounded")
        entry = self.update["masters"][self.identity]
        previous = entry["previous_files"]["numerical.json"]
        expected = {key: previous[key] for key in ["path", "sha256"]}
        self.assertTrue(
            precision.accepts_producer_binding(
                expected, self.master, "numerical.json", self.root
            )
        )
        self.assertFalse(
            precision.accepts_producer_binding(
                {**expected, "sha256": "0" * 64},
                self.master,
                "numerical.json",
                self.root,
            )
        )

    def test_rejects_changed_unselected_rows_even_with_updated_checksums(self):
        entry = self.update["masters"][self.identity]
        relative = entry["files"]["numerical.json"]["path"]
        data.write_json(
            self.root / "4L" / relative, [[-1, "3"], [0, "1.2500000"], [1, "3.5000000"]]
        )
        checksum = data.digest(self.root / "4L" / relative)
        entry["files"]["numerical.json"]["sha256"] = checksum
        self.master["files"]["numerical.json"]["sha256"] = checksum
        with self.assertRaisesRegex(ValueError, "unselected epsilon"):
            precision.validate_master(self.update, self.master, self.root)

    def test_rejects_forged_original_payload_and_nonfinite_error_bound(self):
        self.update["masters"][self.identity]["previous_files"]["numerical.json"][
            "contents"
        ] += " "
        with self.assertRaisesRegex(ValueError, "binding differs"):
            precision.validate_master(self.update, self.master, self.root)
        for value in ["NaN", "Infinity", "-1", "0", 1]:
            update = copy.deepcopy(self.update)
            update["masters"][self.identity]["coefficients"][0]["absolute_error"] = (
                value
            )
            with self.subTest(value=value), self.assertRaises(ValueError):
                precision.coefficients(update, {self.identity: self.master})

    def test_rejects_identity_changes_and_false_exactness(self):
        for field, value in [
            ("symbolic", True),
            ("significant_digits", True),
            ("error_quality", "estimated"),
            ("stored_significant_digits", 3),
        ]:
            update = copy.deepcopy(self.update)
            update["masters"][self.identity]["coefficients"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                precision.coefficients(update, {self.identity: self.master})

    def test_numerical_upgrade_preserves_independently_accepted_exact_formulas(self):
        entry = self.update["masters"][self.identity]
        relative = entry["files"]["symbolic.json"]["path"]
        path = self.root / "4L" / relative
        data.write_json(path, [[-1, "2"], [0, "K5Moment(1)"], [1, "K5LogMoment(1)"]])
        checksum = data.digest(path)
        entry["accepted_symbolic"] = {
            "path": relative,
            "sha256": checksum,
            "contents": path.read_text(),
        }
        entry["files"]["symbolic.json"]["sha256"] = checksum
        self.master["files"]["symbolic.json"]["sha256"] = checksum
        for row in entry["coefficients"]:
            row["symbolic"] = True
        precision.validate_master(self.update, self.master, self.root)
        data.write_json(
            path, [[-1, "2"], [0, "invented_formula"], [1, "K5LogMoment(1)"]]
        )
        changed = data.digest(path)
        entry["files"]["symbolic.json"]["sha256"] = changed
        self.master["files"]["symbolic.json"]["sha256"] = changed
        with self.assertRaisesRegex(ValueError, "changed accepted exact"):
            precision.validate_master(self.update, self.master, self.root)


class OracleCoverageCorrectionTests(unittest.TestCase):
    def setUp(self):
        self.provenance = data.read_json(data.ROOT / precision.RECEIPT)["provenance"]
        self.archive = (data.ROOT / self.provenance["validation"]["path"]).parent

    def test_addendum_completes_the_actual_required_anchor_set(self):
        precision.validate_oracle_coverage(data.ROOT, self.provenance, self.archive)

    def test_missing_addendum_and_wrong_original_payload_are_rejected(self):
        missing = copy.deepcopy(self.provenance)
        del missing["oracle_coverage_addendum"]
        with self.assertRaisesRegex(ValueError, "requires the anchor-one"):
            precision.validate_oracle_coverage(data.ROOT, missing, self.archive)
        wrong = copy.deepcopy(self.provenance)
        wrong["payload"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "does not bind"):
            precision.validate_oracle_coverage(data.ROOT, wrong, self.archive)

    def test_another_missing_required_anchor_cannot_hide_behind_the_same_count(self):
        read_json = data.read_json
        oracle_path = self.archive / "mathematica-seeds-v2.json"
        oracle = read_json(oracle_path)
        point = next(
            row
            for row in oracle["rows"]
            if (row["numerator"], row["denominator"]) == (5, 4)
        )
        point["numerator"], point["denominator"] = 7, 8

        def altered_oracle(path):
            return oracle if Path(path) == oracle_path else read_json(path)

        with (
            patch.object(data, "read_json", side_effect=altered_oracle),
            self.assertRaisesRegex(ValueError, "actual Bessel integration anchors"),
        ):
            precision.validate_oracle_coverage(data.ROOT, self.provenance, self.archive)


if __name__ == "__main__":
    unittest.main()
