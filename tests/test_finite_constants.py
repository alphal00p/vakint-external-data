import copy
import sys
import tempfile
import unittest
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
            data.write_json(root / "constants.json", [record, record])
            with self.assertRaisesRegex(ValueError, "identity or capability"):
                finite_constants.binding(root)
            for field, value in [
                ("absolute_error", "NaN"),
                ("absolute_error", "1"),
                ("value", "Infinity"),
                ("significant_digits", True),
            ]:
                changed = copy.deepcopy(record)
                changed[field] = value
                data.write_json(root / "constants.json", [changed])
                with (
                    self.subTest(field=field, value=value),
                    self.assertRaises(ValueError),
                ):
                    finite_constants.binding(root)


if __name__ == "__main__":
    unittest.main()
