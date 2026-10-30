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

    def source_fixture(self):
        update = copy.deepcopy(self.update)
        entry = update["masters"][self.identity]
        rows = []
        values = dict(data.read_json(self.root / "4L/masters/P6/numerical.json"))
        for row in entry["coefficients"]:
            power = row["epsilon_power"]
            symbol = f"fixture_ep{power}"
            entry["sources"][str(power)]["symbol"] = symbol
            rows.append(
                {
                    "symbol": symbol,
                    "master_basis": "vakint::PR4",
                    "epsilon_power": power,
                    "normalization": "FMFTandMATAD",
                    "significant_digits": row["significant_digits"],
                    "stored_significant_digits": row["stored_significant_digits"],
                    "numerical_value": values[power],
                    "validation": {"absolute_error_bound": row["absolute_error"]},
                }
            )
        for name, previous in entry["previous_files"].items():
            previous["archive"] = f"provenance/previous/{name}"
            path = self.root / previous["archive"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(previous["contents"])
        update["provenance"] = {}
        for name, contents in [
            ("payload", {"constants": rows}),
            ("validation", {}),
            ("previous_producer_update", {}),
        ]:
            relative = f"provenance/{name}.json"
            path = self.root / relative
            data.write_json(path, contents)
            update["provenance"][name] = {"path": relative, "sha256": data.digest(path)}
        return update, rows

    def additional_reference(self):
        return {
            "kind": precision.PR11_SOURCE_KIND,
            "payload": {"path": "missing-payload.json", "sha256": "0" * 64},
            "validation": {"path": "missing-validation.json", "sha256": "0" * 64},
            "proof_manifest": {"path": "missing-proof.json", "sha256": "0" * 64},
        }

    def load_fixture(self, update, rows):
        data.write_json(self.root / precision.RECEIPT, update)
        # These tests isolate selection after acceptance; real Bessel acceptance
        # is exercised against its immutable archive in the tests below.
        with patch.object(precision, "_load_bessel_source", return_value=rows):
            return precision.load_source(self.root)

    def test_missing_source_id_keeps_the_legacy_source_selection(self):
        update, rows = self.source_fixture()
        with patch.object(precision, "_load_pr11_source") as additional:
            self.assertEqual(self.load_fixture(update, rows), update)
            update["provenance"]["additional_sources"] = {}
            self.assertEqual(self.load_fixture(update, rows), update)
            additional.assert_not_called()

    def test_authoritative_symbols_are_scoped_to_the_selected_source(self):
        update, rows = self.source_fixture()
        entry = update["masters"][self.identity]
        rows[1]["symbol"] = rows[0]["symbol"]
        entry["sources"]["1"].update(
            source_id=precision.PR11_SOURCE_ID, symbol=rows[0]["symbol"]
        )
        update["provenance"]["additional_sources"] = {
            precision.PR11_SOURCE_ID: self.additional_reference()
        }
        # Only the adapter is stubbed: two accepted sources may use the same
        # symbol without either source silently replacing the other.
        with patch.object(precision, "_load_pr11_source", return_value=[rows[1]]):
            self.assertEqual(self.load_fixture(update, rows[:1]), update)

    def test_duplicate_authoritative_rows_and_unknown_symbols_are_rejected(self):
        update, rows = self.source_fixture()
        with self.assertRaisesRegex(ValueError, "duplicate authoritative"):
            self.load_fixture(update, [*rows, rows[0]])
        update["masters"][self.identity]["sources"]["0"]["symbol"] = "missing"
        with self.assertRaisesRegex(ValueError, "unknown authoritative"):
            self.load_fixture(update, rows)

    def test_explicit_unknown_or_null_source_never_falls_back_to_bessel(self):
        original, rows = self.source_fixture()
        for source_id in [precision.PR11_SOURCE_ID, "unknown", "", None, True, []]:
            update = copy.deepcopy(original)
            update["masters"][self.identity]["sources"]["0"]["source_id"] = source_id
            with (
                self.subTest(source_id=source_id),
                self.assertRaisesRegex(
                    ValueError, "unknown numerical precision source id"
                ),
            ):
                self.load_fixture(update, rows)

    def test_malformed_unknown_and_unused_source_declarations_are_rejected(self):
        original, rows = self.source_fixture()
        for additional in [None, [], False, {"unknown": self.additional_reference()}]:
            update = copy.deepcopy(original)
            update["provenance"]["additional_sources"] = additional
            with (
                self.subTest(additional=additional),
                self.assertRaisesRegex(
                    ValueError, "additional numerical precision source"
                ),
            ):
                self.load_fixture(update, rows)
        update = copy.deepcopy(original)
        update["provenance"]["additional_sources"] = {
            precision.PR11_SOURCE_ID: self.additional_reference()
        }
        with (
            patch.object(precision, "_load_pr11_source") as adapter,
            self.assertRaisesRegex(ValueError, "unused additional"),
        ):
            self.load_fixture(update, rows)
        adapter.assert_not_called()

    def test_pr11_accepted_flags_do_not_replace_the_scientific_verifier(self):
        update, rows = self.source_fixture()
        update["masters"][self.identity]["sources"]["0"]["source_id"] = (
            precision.PR11_SOURCE_ID
        )
        reference = self.additional_reference()
        # Existing, hash-consistent evidence with an accepted flag is still
        # insufficient; it must never activate the reserved scientific adapter.
        for name in ["payload", "validation", "proof_manifest"]:
            path = self.root / reference[name]["path"]
            data.write_json(path, {"accepted": True, "constants": rows})
            reference[name]["sha256"] = data.digest(path)
        update["provenance"]["additional_sources"] = {
            precision.PR11_SOURCE_ID: reference
        }
        with self.assertRaisesRegex(ValueError, "unsupported PR11 proof index"):
            self.load_fixture(update, rows)
        for kind in [
            "bessel",
            "python:accept_all",
            "vakint.pr11d.validated-periods.v1",
        ]:
            reference["kind"] = kind
            with (
                self.subTest(kind=kind),
                self.assertRaisesRegex(
                    ValueError, "invalid additional numerical precision source adapter"
                ),
            ):
                self.load_fixture(update, rows)

    def test_pr11_period_name_does_not_promote_symbolic_exactness(self):
        update, rows = self.source_fixture()
        entry = update["masters"][self.identity]
        entry["sources"]["0"]["source_id"] = precision.PR11_SOURCE_ID
        entry["coefficients"][0]["symbolic"] = True
        update["provenance"]["additional_sources"] = {
            precision.PR11_SOURCE_ID: self.additional_reference()
        }
        with (
            patch.object(precision, "_load_pr11_source", return_value=rows),
            self.assertRaisesRegex(ValueError, "remains numerical-only"),
        ):
            self.load_fixture(update, rows)

    def published_fixture(self):
        update, rows = self.source_fixture()
        entry = update["masters"][self.identity]
        entry["sources"]["0"]["source_id"] = precision.PR11_SOURCE_ID
        entry["coefficients"][0]["symbolic"] = True
        update["provenance"]["additional_sources"] = {
            precision.PR11_SOURCE_ID: self.additional_reference()
        }
        contents = json.dumps([[-1, "2"], [0, "-5*symbolica::zeta(5)"], [1, "3.5"]])
        archive = self.root / "provenance/published/P6/symbolic.json"
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_text(contents)
        base = "c" * 40
        entry["accepted_symbolic"] = {
            "source_commit": base,
            "source_publication": "takeover-fixture",
            "path": "masters/P6/symbolic.json",
            "sha256": precision.text_digest(contents),
            "archive": "provenance/published/P6/symbolic.json",
            "contents": contents,
        }
        receipt = self.root / "provenance/published/receipt.json"
        data.write_json(
            receipt,
            {
                "accepted": True,
                "base_commit": base,
                "exact_rows": {
                    self.identity: {"0": precision.text_digest("-5*symbolica::zeta(5)")}
                },
            },
        )
        update["provenance"]["accepted_symbolic_publications"] = {
            "takeover-fixture": {
                "base_commit": base,
                "receipt": {
                    "path": "provenance/published/receipt.json",
                    "sha256": data.digest(receipt),
                },
            }
        }
        return update, rows, receipt

    def test_published_exact_rows_may_mark_pr11_finite_rows_symbolic(self):
        update, rows, receipt = self.published_fixture()
        with patch.object(precision, "_load_pr11_source", return_value=rows):
            self.assertEqual(self.load_fixture(update, rows), update)
        for change, message in [
            (lambda u: u["masters"][self.identity]["accepted_symbolic"].update(source_commit="d" * 40),
             "publication differs"),
            (lambda u: u["provenance"]["accepted_symbolic_publications"]["takeover-fixture"]["receipt"].update(sha256="0" * 64),
             "receipt changed"),
            (lambda u: u["masters"][self.identity]["accepted_symbolic"].update(source_publication="unknown"),
             "publication differs"),
            (lambda u: u["provenance"].update(accepted_symbolic_publications=[]),
             "invalid accepted exact symbolic publications"),
        ]:
            altered = copy.deepcopy(update)
            change(altered)
            with (
                self.subTest(message=message),
                patch.object(precision, "_load_pr11_source", return_value=rows),
                self.assertRaisesRegex(ValueError, message),
            ):
                self.load_fixture(altered, rows)
        # A receipt that does not bind the row text, or omits the row, fails.
        for exact_rows, message in [
            ({self.identity: {"0": precision.text_digest("invented")}}, "row differs"),
            ({self.identity: {"1": precision.text_digest("3.5")}}, "remains numerical-only"),
            ({}, "scope differs"),
        ]:
            altered = copy.deepcopy(update)
            data.write_json(receipt, {"accepted": True, "base_commit": "c" * 40, "exact_rows": exact_rows})
            altered["provenance"]["accepted_symbolic_publications"]["takeover-fixture"]["receipt"]["sha256"] = data.digest(receipt)
            with (
                self.subTest(exact_rows=exact_rows),
                patch.object(precision, "_load_pr11_source", return_value=rows),
                self.assertRaisesRegex(ValueError, message),
            ):
                self.load_fixture(altered, rows)

    def test_incomplete_source_records_and_extra_selection_fields_are_rejected(self):
        update, rows = self.source_fixture()
        source = update["masters"][self.identity]["sources"]["0"]
        source["fallback"] = "bessel"
        with self.assertRaisesRegex(ValueError, "invalid numerical precision source"):
            self.load_fixture(update, rows)
        del source["fallback"]
        source["source_id"] = precision.PR11_SOURCE_ID
        for reference in [{}, None, {"kind": "arbitrary"}]:
            update["provenance"]["additional_sources"] = {
                precision.PR11_SOURCE_ID: reference
            }
            with (
                self.subTest(reference=reference),
                self.assertRaisesRegex(ValueError, "invalid additional"),
            ):
                self.load_fixture(update, rows)


class OracleCoverageCorrectionTests(unittest.TestCase):
    def setUp(self):
        self.provenance = data.read_json(data.ROOT / precision.RECEIPT)["provenance"]
        self.archive = (data.ROOT / self.provenance["validation"]["path"]).parent

    def test_addendum_completes_the_actual_required_anchor_set(self):
        precision.validate_oracle_coverage(data.ROOT, self.provenance, self.archive)

    def test_complete_legacy_source_still_loads_without_any_data_changes(self):
        receipt = data.ROOT / precision.RECEIPT
        original = receipt.read_bytes()
        payload = data.read_json(data.ROOT / self.provenance["payload"]["path"])
        validation = data.read_json(data.ROOT / self.provenance["validation"]["path"])
        self.assertEqual(
            precision._load_bessel_source(
                data.ROOT, self.provenance, payload, validation
            ),
            payload["constants"],
        )
        self.assertEqual(receipt.read_bytes(), original)

    def test_extracted_bessel_acceptance_retains_all_original_flags(self):
        payload = data.read_json(data.ROOT / self.provenance["payload"]["path"])
        validation = data.read_json(data.ROOT / self.provenance["validation"]["path"])
        for field in [
            "accepted",
            "full_gap_free_partitions",
            "complete_infinity_tails",
            "source_pins_unchanged",
            "unique_rounding_cells",
        ]:
            invalid = {**validation, field: False}
            with (
                self.subTest(field=field),
                self.assertRaisesRegex(ValueError, "acceptance is incomplete"),
            ):
                precision._load_bessel_source(
                    data.ROOT, self.provenance, payload, invalid
                )

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
