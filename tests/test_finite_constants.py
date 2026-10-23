import copy
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import data
import finite_constants


class FiniteConstantTests(unittest.TestCase):
    def test_installed_projection_retains_accepted_values_and_proof_bindings(self):
        finite_constants.validate_source(data.ROOT)

    def test_optional_bindings_validate_caps_and_reject_duplicates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertIsNone(finite_constants.binding(root))
            record = {
                "symbol": "vakint::K5Moment(1)",
                "value": "1.23456789",
                "significant_digits": 6,
                "absolute_error": "1e-8",
                "error_quality": "bounded",
                "definition": "test integral",
                "provenance": {"source": "independent certificate"},
            }
            data.write_json(root / "constants.json", [record])
            self.assertEqual(
                finite_constants.binding(root)["sha256"],
                data.digest(root / "constants.json"),
            )
            record["error_quality"] = "estimated"
            data.write_json(root / "constants.json", [record])
            self.assertIsNotNone(finite_constants.binding(root))
            data.write_json(root / "constants.json", [record, record])
            with self.assertRaisesRegex(ValueError, "identity or capability"):
                finite_constants.binding(root)
            for field, value in [
                ("absolute_error", "NaN"),
                ("absolute_error", "1"),
                ("value", "Infinity"),
                ("significant_digits", True),
                ("error_quality", "interval"),
            ]:
                changed = copy.deepcopy(record)
                changed[field] = value
                data.write_json(root / "constants.json", [changed])
                with (
                    self.subTest(field=field, value=value),
                    self.assertRaises(ValueError),
                ):
                    finite_constants.binding(root)

    def test_d2_projection_rejects_changed_centers_caps_quality_and_previous_values(
        self,
    ):
        receipt = data.read_json(data.ROOT / finite_constants.RECEIPT)
        reference = receipt["additional_sources"]["independent-d2-v1"]
        actual = {
            record["symbol"]: record
            for record in data.read_json(data.ROOT / "4L/constants.json")
        }
        for symbol, field, value in [
            ("vakint::PR7D2", "significant_digits", 216),
            ("vakint::PR10D2", "value", "1"),
            ("vakint::PR15D2", "absolute_error", "0"),
            ("vakint::PR7D2", "error_quality", "bounded"),
            ("vakint::K5Moment(1)", "value", "1"),
        ]:
            altered = copy.deepcopy(actual)
            altered[symbol][field] = value
            with (
                self.subTest(symbol=symbol, field=field),
                self.assertRaises(ValueError),
            ):
                finite_constants._validate_d2_source(data.ROOT, reference, altered)

    def test_d2_decimal_envelopes_retain_both_accepted_profiles_exactly(self):
        records = {
            r["symbol"]: r for r in data.read_json(data.ROOT / "4L/constants.json")
        }
        source = data.read_json(
            data.ROOT / "4L/provenance/PR10-PR15-v24/independent-D2-periods-v1.json"
        )

        def scaled(value):
            return Fraction(int(value["integer"])) * Fraction(10) ** value["power10"]

        for period in source["periods"]:
            record = records[period["public_atom"]["readable"]]
            profiles = period["current_independent_auxiliary_evidence"][
                "qualified_bindings"
            ]
            center = Fraction(record["value"])
            error = Fraction(record["absolute_error"])
            self.assertEqual(center, scaled(profiles[1]["center"]))
            self.assertEqual(
                error,
                max(
                    abs(center - scaled(profile["center"]))
                    + scaled(profile["error_upper"])
                    for profile in profiles
                ),
            )
            self.assertLess(error, abs(center) * Fraction(10) ** -215)
            self.assertEqual(record["significant_digits"], 215)
            self.assertEqual(record["error_quality"], "estimated")


if __name__ == "__main__":
    unittest.main()
