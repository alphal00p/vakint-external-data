import copy
import json
import sys
import tempfile
import unittest
from decimal import Decimal, localcontext
from unittest import mock
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import data
import finite_constants
from d2_constants import archive

BEFORE_V3 = "provenance/takeover-4l-closures-runtime-v3/before/4L/constants.json"


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
        # The 215-digit v1 records were superseded by takeover-4l-closures-v3;
        # the v1 projection replays unchanged against that adapter's before-image.
        actual = {
            record["symbol"]: record
            for record in data.read_json(data.ROOT / BEFORE_V3)
            if record["symbol"] not in {"vakint::PR7D2Eps1", "vakint::PR10D2Eps1"}
        }
        finite_constants._validate_d2_source(data.ROOT, reference, actual)
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
        records = {r["symbol"]: r for r in data.read_json(data.ROOT / BEFORE_V3)}
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

    def test_taylor_projection_preserves_all_seven_previous_records(self):
        receipt = data.read_json(data.ROOT / finite_constants.RECEIPT)
        reference = receipt["additional_sources"]["independent-d2-taylor01-v2"]
        actual = {
            record["symbol"]: record for record in data.read_json(data.ROOT / BEFORE_V3)
        }
        extra = finite_constants._validate_d2_taylor01_source(
            data.ROOT, reference, actual
        )
        self.assertEqual(set(extra), {"vakint::PR7D2Eps1", "vakint::PR10D2Eps1"})
        for symbol, field, value in [
            ("vakint::PR7D2Eps1", "significant_digits", 216),
            ("vakint::PR10D2Eps1", "value", "1"),
            ("vakint::PR7D2Eps1", "absolute_error", "0"),
            ("vakint::PR10D2Eps1", "error_quality", "bounded"),
            ("vakint::PR7D2", "value", "1"),
            ("vakint::K5Moment(1)", "value", "1"),
        ]:
            altered = copy.deepcopy(actual)
            altered[symbol][field] = value
            with (
                self.subTest(symbol=symbol, field=field),
                self.assertRaises(ValueError),
            ):
                finite_constants._validate_d2_taylor01_source(
                    data.ROOT, reference, altered
                )
        del actual["vakint::PR15D2"]
        with self.assertRaisesRegex(ValueError, "previous finite constant records"):
            finite_constants._validate_d2_taylor01_source(data.ROOT, reference, actual)

    def test_taylor_envelopes_include_both_full_profile_neighborhoods_exactly(self):
        records = data.read_json(
            data.ROOT
            / "provenance/independent-d2-taylor01-runtime-v2/constants-d2-taylor01.json"
        )
        index = data.read_json(
            data.ROOT
            / "provenance/independent-d2-taylor01-runtime-v2/portable-proof-index.json"
        )
        for record in records:
            center, error = Fraction(record["value"]), Fraction(record["absolute_error"])
            neighborhoods = []
            for neighborhood in record["provenance"]["profile_neighborhoods"]:
                profile, _ = archive(
                    data.ROOT, index, neighborhood["source"]["uncompressed_sha256"]
                )
                position = int(neighborhood["center_json_pointer"].split("/")[2])
                model = profile["coefficient_models"][position]
                profile_center = Fraction(model["center"][0])
                profile_error = Fraction(model["total_empirical_error_abs"][0])
                neighborhoods.append((profile_center, profile_error))
                self.assertLessEqual(abs(center - profile_center) + profile_error, error)
            self.assertEqual(len(neighborhoods), 2)
            self.assertEqual(center, neighborhoods[1][0])
            self.assertEqual(
                error, max(abs(center - c) + e for c, e in neighborhoods)
            )
            self.assertLess(error, abs(center) * Fraction(10) ** -215)
            self.assertEqual(record["significant_digits"], 215)
            self.assertEqual(record["error_quality"], "estimated")

    def test_takeover_v3_owns_lifted_and_new_records_with_definitions(self):
        receipt = data.read_json(data.ROOT / finite_constants.RECEIPT)
        reference = receipt["additional_sources"][finite_constants.TAKEOVER_V3]
        actual = {
            record["symbol"]: record
            for record in data.read_json(data.ROOT / "4L/constants.json")
        }
        owned, previous, superseded = finite_constants._validate_takeover_v3_source(
            data.ROOT, reference, actual
        )
        self.assertEqual(len(owned), 46)
        self.assertEqual(len(actual), 50)
        self.assertEqual(
            superseded,
            {
                "vakint::PR7D2",
                "vakint::PR10D2",
                "vakint::PR15D2",
                "vakint::PR7D2Eps1",
                "vakint::PR10D2Eps1",
            },
        )
        self.assertEqual(len(previous), 9)
        for symbol in superseded:
            self.assertEqual(previous[symbol]["significant_digits"], 215)
            self.assertGreaterEqual(owned[symbol]["significant_digits"], 520)
            self.assertEqual(
                owned[symbol]["definition"], previous[symbol]["definition"]
            )
        for record in actual.values():
            finite_constants.lint_symbolic_definition(record["symbolic_definition"])
            with localcontext() as context:
                context.prec = record["significant_digits"] + 50
                value = Decimal(record["value"])
                self.assertGreater(len(value.as_tuple().digits), record["significant_digits"])
        for symbol, field, value in [
            ("vakint::PR9D2Eps1", "value", "1"),
            ("vakint::PR7D2", "significant_digits", 215),
            ("vakint::PR10D2Eps4", "absolute_error", "0"),
            ("vakint::T111bar5", "error_quality", "bounded"),
            ("vakint::s6weak", "symbolic_definition", "vakint::Integral(1,vakint::Interval(vakint::t,0,1))"),
            ("vakint::K5Moment(1)", "symbolic_definition", "vakint::K5Moment(1)"),
            ("vakint::K5LogMoment(3)", "value", "1"),
        ]:
            altered = copy.deepcopy(actual)
            altered[symbol][field] = value
            with (
                self.subTest(symbol=symbol, field=field),
                self.assertRaises(ValueError),
            ):
                finite_constants._validate_takeover_v3_source(
                    data.ROOT, reference, altered
                )
        altered = copy.deepcopy(actual)
        del altered["vakint::K5Moment(3)"]["symbolic_definition"]
        with self.assertRaisesRegex(ValueError, "retained finite constant records"):
            finite_constants._validate_takeover_v3_source(data.ROOT, reference, altered)
        altered = copy.deepcopy(actual)
        del altered["vakint::PR0D2Eps2"]
        with self.assertRaises(ValueError):
            finite_constants._validate_takeover_v3_source(data.ROOT, reference, altered)

    def test_takeover_v3_rejects_changed_before_image_and_unknown_adapter(self):
        receipt = data.read_json(data.ROOT / finite_constants.RECEIPT)
        reference = receipt["additional_sources"][finite_constants.TAKEOVER_V3]
        actual = {
            record["symbol"]: record
            for record in data.read_json(data.ROOT / "4L/constants.json")
        }
        original = data.digest

        def changed_before(path):
            if str(path).endswith(BEFORE_V3):
                return "0" * 64
            return original(path)

        with (
            mock.patch.object(finite_constants.data, "digest", changed_before),
            self.assertRaisesRegex(ValueError, "before-image changed"),
        ):
            finite_constants._validate_takeover_v3_source(data.ROOT, reference, actual)
        reader = data.read_json

        def unknown_adapter(path):
            value = reader(path)
            if str(path).endswith(finite_constants.RECEIPT):
                value = copy.deepcopy(value)
                value["additional_sources"]["takeover-unknown-v9"] = reference
            return value

        with (
            mock.patch.object(finite_constants.data, "read_json", unknown_adapter),
            self.assertRaisesRegex(ValueError, "unknown finite constant source adapter"),
        ):
            finite_constants.validate_source(data.ROOT)

        def changed_supersession(path):
            value = reader(path)
            if str(path).endswith("takeover-4l-closures-runtime-v3/projection.json"):
                value = copy.deepcopy(value)
                value["superseded_symbols"] = value["superseded_symbols"][1:]
            return value

        with (
            mock.patch.object(finite_constants.data, "read_json", changed_supersession),
            self.assertRaises(ValueError),
        ):
            finite_constants._validate_takeover_v3_source(data.ROOT, reference, actual)

    def test_takeover_v3_envelopes_recompute_exactly_from_archives(self):
        from d2_constants import archive_bytes

        registry = data.read_json(
            data.ROOT
            / "4L/provenance/takeover-4L-closures-v1/independent-D2-period-registry-v3.json"
        )
        index = data.read_json(
            data.ROOT / "provenance/takeover-4l-closures-runtime-v3/portable-proof-index.json"
        )
        records = {
            r["symbol"]: r for r in data.read_json(data.ROOT / "4L/constants.json")
        }
        sys.set_int_max_str_digits(0)
        for period in registry["periods"]:
            cell = period["value_cell"]
            raw, _ = archive_bytes(data.ROOT, index, cell["source_uncompressed_sha256"])
            source = json.loads(raw, parse_float=str)
            node = source
            for part in cell["center_json_pointer"].split("/")[1:]:
                node = node[int(part)] if isinstance(node, list) else node[part]
            if cell["negate_raw_to_hat"]:
                node = node[1:] if node.startswith("-") else "-" + node
            record = records[period["public_symbol"]]
            self.assertEqual(record["value"], node)
            center, error = Fraction(record["value"]), Fraction(record["absolute_error"])
            self.assertLess(
                error, abs(center) * Fraction(10) ** -record["significant_digits"]
            )
            self.assertEqual(record["error_quality"], "estimated")
            self.assertEqual(record["symbolic_definition"], period["symbolic_definition"])

    def test_symbolic_definition_lint_rejects_floats_unbound_and_unknown_heads(self):
        good = "vakint::Integral(vakint::t^3*(symbolica::bessel_k(0,vakint::t))^5,vakint::Interval(vakint::t,0,∞))"
        finite_constants.lint_symbolic_definition(good)
        for bad in [
            "",
            "1.5*vakint::Integral(vakint::t,vakint::Interval(vakint::t,0,1))",
            "vakint::Integral(vakint::t,vakint::Interval(vakint::t,0,1e-3))",
            "vakint::PR7D2",
            "vakint::Integral(vakint::t,vakint::Interval(vakint::t,0,1)",
            "vakint::SeriesCoefficient(vakint::delta^2,vakint::ep,0,1)",
            "vakint::k(1)",
            "vakint::Integral(vakint::x(2),vakint::Interval(vakint::x(1),0,1))",
            "python::f(vakint::t)",
        ]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                finite_constants.lint_symbolic_definition(bad)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            record = {
                "symbol": "vakint::K5Moment(1)",
                "value": "1.23456789",
                "significant_digits": 6,
                "absolute_error": "1e-8",
                "error_quality": "bounded",
                "definition": "test integral",
                "provenance": {"source": "independent certificate"},
                "symbolic_definition": good,
            }
            data.write_json(root / "constants.json", [record])
            self.assertIsNotNone(finite_constants.binding(root))
            record["symbolic_definition"] = "vakint::Unknown(1)"
            data.write_json(root / "constants.json", [record])
            with self.assertRaises(ValueError):
                finite_constants.binding(root)
            record["symbolic_definition"] = good
            record["extra_field"] = 1
            data.write_json(root / "constants.json", [record])
            with self.assertRaisesRegex(ValueError, "binding fields"):
                finite_constants.binding(root)


if __name__ == "__main__":
    unittest.main()
