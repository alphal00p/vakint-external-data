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
# The takeover records were superseded for 45 symbols by precision-lift-4l-v4; the
# takeover projection replays unchanged against that adapter's before-image.
BEFORE_V4 = "provenance/precision-lift-4l-runtime-v4/before/4L/constants.json"
LIFT_V4_REGISTRY = "provenance/precision-lift-4l-runtime-v4/registry.json"
LIFT_V4_INDEX = "provenance/precision-lift-4l-runtime-v4/portable-proof-index.json"
TWO_PROFILE = {
    "vakint::PR12D2Eps2",
    "vakint::PR12D2Eps3",
    "vakint::PR15D2Eps1",
    "vakint::PR15D2Eps2",
    "vakint::PR15D2Eps3",
    "vakint::PR0D2Eps1",
    "vakint::PR0D2Eps2",
}


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
            for record in data.read_json(data.ROOT / BEFORE_V4)
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
            for record in data.read_json(data.ROOT / BEFORE_V4)
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
        records = {r["symbol"]: r for r in data.read_json(data.ROOT / BEFORE_V4)}
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

    def test_takeover_v3_errors_include_storage_rounding(self):
        import d2_constants

        registry_path = d2_constants.TAKEOVER_V3_REGISTRY
        index_path = d2_constants.TAKEOVER_V3_INDEX
        index = data.read_json(data.ROOT / index_path)
        live = {r["symbol"]: r for r in data.read_json(data.ROOT / BEFORE_V4)}
        registry = data.read_json(data.ROOT / registry_path)
        owned = {period["public_symbol"] for period in registry["periods"]}
        for symbol in owned:
            record = live[symbol]
            with self.subTest(symbol=symbol):
                unit = Decimal(1).scaleb(Decimal(record["value"]).as_tuple().exponent)
                self.assertGreaterEqual(Decimal(record["absolute_error"]), unit)

        def derive_with(mutate):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                for archive_entry in index["archives"]:
                    relative = archive_entry["portable_archive"]["path"]
                    (root / relative).parent.mkdir(parents=True, exist_ok=True)
                    (root / relative).write_bytes((data.ROOT / relative).read_bytes())
                (root / index_path).write_bytes((data.ROOT / index_path).read_bytes())
                changed = copy.deepcopy(registry)
                mutate(changed)
                data.write_json(root / registry_path, changed)
                return d2_constants.derive_takeover_v3(root)

        records, _, _ = derive_with(lambda registry: None)
        self.assertEqual([r["symbol"] for r in records], [p["public_symbol"] for p in registry["periods"]])

        def cell(changed, symbol):
            return next(
                p["value_cell"] for p in changed["periods"] if p["public_symbol"] == symbol
            )

        def drop_unit(changed):
            terms = cell(changed, "vakint::PR9D2Eps1")["error_terms"]
            terms[:] = [t for t in terms if t["kind"] != "last_digit_unit"]

        def double_unit(changed):
            cell(changed, "vakint::T111bar5")["error_terms"].append({"kind": "last_digit_unit"})

        for mutate in [drop_unit, double_unit]:
            with self.subTest(mutation=mutate.__name__), self.assertRaisesRegex(
                ValueError, "storage rounding"
            ):
                derive_with(mutate)
        with (
            mock.patch.object(d2_constants, "takeover_v3_error", return_value=Decimal(0)),
            self.assertRaisesRegex(ValueError, "below the storage rounding"),
        ):
            derive_with(lambda registry: None)

    def test_precision_lift_v4_supersedes_45_records_inside_their_previous_errors(self):
        receipt = data.read_json(data.ROOT / finite_constants.RECEIPT)
        reference = receipt["additional_sources"][finite_constants.PRECISION_LIFT_V4]
        actual = {
            record["symbol"]: record
            for record in data.read_json(data.ROOT / "4L/constants.json")
        }
        owned, previous, superseded = finite_constants._validate_precision_lift_v4_source(
            data.ROOT, reference, actual
        )
        self.assertEqual(len(owned), 45)
        self.assertEqual(superseded, set(owned))
        self.assertEqual(set(previous), set(actual))
        self.assertEqual(set(actual) - superseded, {
            "vakint::K5Moment(1)",
            "vakint::K5Moment(3)",
            "vakint::K5LogMoment(1)",
            "vakint::K5LogMoment(3)",
            "vakint::s6weak",
        })
        with localcontext() as context:
            context.prec = 25000
            for symbol in superseded:
                new, old = owned[symbol], previous[symbol]
                with self.subTest(symbol=symbol):
                    self.assertGreater(new["significant_digits"], old["significant_digits"])
                    self.assertGreaterEqual(new["significant_digits"], 2348)
                    self.assertLessEqual(
                        abs(Decimal(new["value"]) - Decimal(old["value"])),
                        Decimal(old["absolute_error"]),
                    )
                    for field in ["definition", "symbolic_definition", "error_quality"]:
                        self.assertEqual(new[field], old[field])
                    self.assertEqual(
                        new["provenance"]["definition_metadata"],
                        old["provenance"]["definition_metadata"],
                    )
        for symbol, field, value in [
            ("vakint::PR7D2", "value", "1"),
            ("vakint::PR0D2Eps1", "significant_digits", 2396),
            ("vakint::BNbar5", "absolute_error", "0"),
            ("vakint::T111bar5", "error_quality", "bounded"),
            ("vakint::PR12D2Eps3", "symbolic_definition", "vakint::Integral(1,vakint::Interval(vakint::t,0,1))"),
            ("vakint::K5Moment(1)", "value", "1"),
            ("vakint::s6weak", "significant_digits", 20001),
        ]:
            altered = copy.deepcopy(actual)
            altered[symbol][field] = value
            with (
                self.subTest(symbol=symbol, field=field),
                self.assertRaises(ValueError),
            ):
                finite_constants._validate_precision_lift_v4_source(
                    data.ROOT, reference, altered
                )
        altered = copy.deepcopy(actual)
        del altered["vakint::PR9D2Eps1"]
        with self.assertRaises(ValueError):
            finite_constants._validate_precision_lift_v4_source(data.ROOT, reference, altered)

    def test_precision_lift_v4_rejects_changed_before_image_and_orphan_adapter(self):
        receipt = data.read_json(data.ROOT / finite_constants.RECEIPT)
        reference = receipt["additional_sources"][finite_constants.PRECISION_LIFT_V4]
        actual = {
            record["symbol"]: record
            for record in data.read_json(data.ROOT / "4L/constants.json")
        }
        original = data.digest

        def changed_before(path):
            if str(path).endswith(BEFORE_V4):
                return "0" * 64
            return original(path)

        with (
            mock.patch.object(finite_constants.data, "digest", changed_before),
            self.assertRaisesRegex(ValueError, "before-image changed"),
        ):
            finite_constants._validate_precision_lift_v4_source(data.ROOT, reference, actual)
        reader = data.read_json

        def without_takeover(path):
            value = reader(path)
            if str(path).endswith(finite_constants.RECEIPT):
                value = copy.deepcopy(value)
                del value["additional_sources"][finite_constants.TAKEOVER_V3]
            return value

        with (
            mock.patch.object(finite_constants.data, "read_json", without_takeover),
            self.assertRaisesRegex(ValueError, "needs the takeover adapter"),
        ):
            finite_constants.validate_source(data.ROOT)

        def changed_supersession(path):
            value = reader(path)
            if str(path).endswith("precision-lift-4l-runtime-v4/projection.json"):
                value = copy.deepcopy(value)
                value["superseded_symbols"] = value["superseded_symbols"][1:]
            return value

        with (
            mock.patch.object(finite_constants.data, "read_json", changed_supersession),
            self.assertRaises(ValueError),
        ):
            finite_constants._validate_precision_lift_v4_source(data.ROOT, reference, actual)

    def test_precision_lift_v4_centres_are_the_validated_digits_and_recompute_exactly(self):
        from d2_constants import archive_bytes

        registry = data.read_json(data.ROOT / LIFT_V4_REGISTRY)
        index = data.read_json(data.ROOT / LIFT_V4_INDEX)
        records = {r["symbol"]: r for r in data.read_json(data.ROOT / "4L/constants.json")}
        sys.set_int_max_str_digits(0)
        self.assertEqual(len(registry["periods"]), 45)
        for period in registry["periods"]:
            cell, symbol = period["value_cell"], period["public_symbol"]
            raw, _ = archive_bytes(data.ROOT, index, cell["source_uncompressed_sha256"])
            source = json.loads(raw, parse_float=str)

            def walk(pointer):
                node = source
                for part in pointer.split("/")[1:]:
                    node = node[int(part)] if isinstance(node, list) else node[part]
                return node

            record = records[symbol]
            with self.subTest(symbol=symbol):
                self.assertEqual(walk(cell["source_symbol_json_pointer"]), symbol)
                self.assertEqual(record["value"], walk(cell["center_json_pointer"]))
                stored = len(Decimal(record["value"]).as_tuple().digits)
                self.assertEqual(stored, walk(cell["validated_digits_json_pointer"]))
                self.assertLess(record["significant_digits"], stored)
                center = Fraction(record["value"])
                unit = Fraction(10) ** Decimal(record["value"]).as_tuple().exponent
                exact = unit
                for term in cell["error_terms"]:
                    if term["kind"] == "abs":
                        exact += Fraction(walk(term["pointer"]))
                    elif term["kind"] == "rel_floor":
                        floor = int(Fraction(walk(term["pointer"])))
                        exact += abs(center) * Fraction(10) ** -(floor + term["offset"])
                error = Fraction(record["absolute_error"])
                self.assertGreaterEqual(error, exact)
                self.assertLess(error, exact * Fraction(1000001, 1000000) + unit)
                self.assertLess(error, abs(center) * Fraction(10) ** -record["significant_digits"])
                self.assertEqual(record["error_quality"], "estimated")
                validation = record["provenance"]["validation"]
                self.assertEqual(validation["prec_validated_digits"], stored)
                self.assertTrue(validation["digits_label"])
                if symbol in TWO_PROFILE:
                    self.assertTrue(validation["digits_label"].startswith("two profiles of one code"))
                    self.assertIs(validation["independent"], False)

    def test_precision_lift_v4_derivation_rejects_tampered_cells(self):
        import d2_constants

        registry = data.read_json(data.ROOT / LIFT_V4_REGISTRY)
        index = data.read_json(data.ROOT / LIFT_V4_INDEX)

        def derive_with(mutate):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                for archive_entry in index["archives"]:
                    relative = archive_entry["portable_archive"]["path"]
                    (root / relative).parent.mkdir(parents=True, exist_ok=True)
                    (root / relative).write_bytes((data.ROOT / relative).read_bytes())
                (root / LIFT_V4_INDEX).write_bytes((data.ROOT / LIFT_V4_INDEX).read_bytes())
                changed = copy.deepcopy(registry)
                mutate(changed)
                data.write_json(root / LIFT_V4_REGISTRY, changed)
                return d2_constants.derive_precision_lift_v4(root)

        records, _ = derive_with(lambda registry: None)
        self.assertEqual(
            [r["symbol"] for r in records], [p["public_symbol"] for p in registry["periods"]]
        )

        def cell(changed, symbol):
            return next(
                p["value_cell"] for p in changed["periods"] if p["public_symbol"] == symbol
            )

        def shorter_center(changed):
            cell(changed, "vakint::PR7D2")["center"] = cell(changed, "vakint::PR7D2")["center"][:-1]

        def drop_unit(changed):
            terms = cell(changed, "vakint::PR0D2Eps1")["error_terms"]
            terms[:] = [t for t in terms if t["kind"] != "last_digit_unit"]

        def claim_all_stored(changed):
            entry = cell(changed, "vakint::BNbar5")
            entry["validated_significant_digits"] = len(Decimal(entry["center"]).as_tuple().digits)

        def other_symbol(changed):
            entry = cell(changed, "vakint::T111bar5")
            entry["source_symbol_json_pointer"] = cell(changed, "vakint::BNbar5")["source_symbol_json_pointer"]

        def stale_registry_flag(changed):
            changed["stored_digits_are_the_validated_digits"] = False

        for mutate, message in [
            (shorter_center, "center differs"),
            (drop_unit, "storage rounding"),
            (claim_all_stored, "finite cap differs"),
            (other_symbol, "names another constant"),
            (stale_registry_flag, "registry authentication"),
        ]:
            with self.subTest(mutation=mutate.__name__), self.assertRaisesRegex(
                ValueError, message
            ):
                derive_with(mutate)

    def test_precision_lift_keeps_formula_evaluations_bound_to_superseded_records(self):
        import precision_supplement

        before = precision_supplement._precision_lift_before_image(data.ROOT)
        self.assertEqual(len(before), 45)
        self.assertTrue(all(r["significant_digits"] <= 650 for r in before))
        precision_supplement.load_source(data.ROOT)
        original = data.digest

        def changed_before(path):
            if str(path).endswith(BEFORE_V4):
                return "0" * 64
            return original(path)

        with (
            mock.patch.object(precision_supplement.data, "digest", changed_before),
            self.assertRaisesRegex(ValueError, "precision-lift before-image changed"),
        ):
            precision_supplement._precision_lift_before_image(data.ROOT)

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
