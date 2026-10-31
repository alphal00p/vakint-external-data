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

    def formula_fixture(self):
        """A Bessel-supplemented fixture whose epsilon^-1 row is evaluated from its exact row."""
        update, rows = self.source_fixture()
        entry = update["masters"][self.identity]
        formula, value, previous = "vakint::C1/3", "2.0000000000", "1.9999"
        base = "e" * 40
        # epsilon^2 is an unselected row that every file must keep unchanged.
        files = {
            "numerical.json": [[-1, value], [0, "1.2500000"], [1, "3.5000000"], [2, "7"]],
            "symbolic.json": [[-1, formula], [0, "1.2500000"], [1, "3.5000000"], [2, "7"]],
        }
        olds = {
            "numerical.json": [[-1, previous], [0, "1.25"], [1, "3.5"], [2, "7"]],
            "symbolic.json": [[-1, formula], [0, "1.25"], [1, "3.5"], [2, "7"]],
        }
        for name, rows_ in files.items():
            path = self.root / "4L" / entry["files"][name]["path"]
            data.write_json(path, rows_)
            record = {"path": entry["files"][name]["path"], "sha256": data.digest(path)}
            entry["files"][name] = record
            self.master["files"][name] = record.copy()
            contents = json.dumps(olds[name]) + "\n"
            archived = self.root / entry["previous_files"][name]["archive"]
            archived.write_text(contents)
            entry["previous_files"][name].update(
                contents=contents, sha256=precision.text_digest(contents)
            )
        symbolic = self.root / "4L" / entry["files"]["symbolic.json"]["path"]
        archive = self.root / "provenance/formula/accepted/symbolic.json"
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_text(symbolic.read_text())
        entry["accepted_symbolic"] = {
            "source_commit": base,
            "source_publication": precision.FORMULA_SOURCE_ID,
            "path": entry["files"]["symbolic.json"]["path"],
            "sha256": data.digest(symbolic),
            "archive": "provenance/formula/accepted/symbolic.json",
            "contents": symbolic.read_text(),
        }
        entry["coefficients"].insert(
            0,
            {
                "epsilon_power": -1,
                "symbolic": True,
                "numerical": True,
                "significant_digits": 10,
                "stored_significant_digits": 11,
                "absolute_error": "1e-12",
                "error_quality": "estimated",
            },
        )
        key = f"{self.identity}:-1"
        entry["sources"]["-1"] = {
            "source_id": precision.FORMULA_SOURCE_ID,
            "symbol": key,
            "numerical_sha256": precision.text_digest(value),
        }
        data.write_json(
            self.root / "4L/constants.json",
            [{"symbol": "vakint::C1", "value": "6.00000000000000", "significant_digits": 14}],
        )
        evidence = self.root / "validation/formula-evidence.json.gz"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_bytes(b"fixture evidence")
        index = self.root / "provenance/formula/portable-proof-index.json"
        data.write_json(
            index,
            {
                "schema": "vakint.external-data.portable-producer-evidence-index.v1",
                "archives": [
                    {
                        "portable_archive": {
                            "path": "validation/formula-evidence.json.gz",
                            **data.file_record(evidence),
                        }
                    }
                ],
            },
        )
        receipt = {
            "schema": precision.FORMULA_RECEIPT_SCHEMA,
            "accepted": True,
            "base_commit": base,
            "error_quality": "estimated",
            "digit_cap": precision.FORMULA_DIGIT_CAP,
            "working_decimal_digits": [20100, 20200],
            "portable_proof_index": {
                "path": "provenance/formula/portable-proof-index.json",
                "sha256": data.digest(index),
            },
            "rows": {
                key: {
                    "loop_count": 4,
                    "master_id": self.identity,
                    "master_basis": "vakint::PR4",
                    "epsilon_power": -1,
                    "normalization": "FMFTandMATAD",
                    "formula_sha256": precision.text_digest(formula),
                    "value_sha256": precision.text_digest(value),
                    "significant_digits": 10,
                    "stored_significant_digits": 11,
                    "absolute_error": "1e-12",
                    "error_quality": "estimated",
                    "finite_constants": {
                        "vakint::C1": {
                            "significant_digits": 14,
                            "value_sha256": precision.text_digest("6.00000000000000"),
                        }
                    },
                    "previous": {
                        "value_sha256": precision.text_digest(previous),
                        "significant_digits": 4,
                        "absolute_error": None,
                    },
                }
            },
            "exact_rows": {self.identity: {"-1": precision.text_digest(formula)}},
        }
        update["provenance"]["additional_sources"] = {
            precision.FORMULA_SOURCE_ID: {"kind": precision.FORMULA_SOURCE_KIND}
        }
        update["provenance"]["accepted_symbolic_publications"] = {
            precision.FORMULA_SOURCE_ID: {"base_commit": base}
        }
        self.write_formula_receipt(update, receipt)
        return update, rows, receipt

    def write_formula_receipt(self, update, receipt):
        path = self.root / "provenance/formula/receipt.json"
        data.write_json(path, receipt)
        reference = {"path": "provenance/formula/receipt.json", "sha256": data.digest(path)}
        update["provenance"]["additional_sources"][precision.FORMULA_SOURCE_ID][
            "receipt"
        ] = reference
        update["provenance"]["accepted_symbolic_publications"][
            precision.FORMULA_SOURCE_ID
        ]["receipt"] = dict(reference)

    def rewrite_value(self, update, receipt, value):
        entry = update["masters"][self.identity]
        path = self.root / "4L" / entry["files"]["numerical.json"]["path"]
        rows = data.read_json(path)
        rows[0][1] = value
        data.write_json(path, rows)
        record = {"path": entry["files"]["numerical.json"]["path"], "sha256": data.digest(path)}
        entry["files"]["numerical.json"] = record
        self.master["files"]["numerical.json"] = record.copy()
        entry["sources"]["-1"]["numerical_sha256"] = precision.text_digest(value)
        receipt["rows"][f"{self.identity}:-1"]["value_sha256"] = precision.text_digest(value)
        self.write_formula_receipt(update, receipt)

    def test_formula_evaluation_admits_estimated_values_of_exact_rows(self):
        update, rows, receipt = self.formula_fixture()
        self.assertEqual(self.load_fixture(update, rows), update)
        selected = precision.coefficients(update, {self.identity: self.master})
        self.assertEqual(selected[self.identity][-1]["error_quality"], "estimated")
        self.assertEqual(selected[self.identity][0]["error_quality"], "bounded")
        precision.validate_master(update, self.master, self.root)

    def test_formula_evaluation_quality_is_tied_to_its_source(self):
        update, rows, receipt = self.formula_fixture()
        known = {self.identity: self.master}
        for power, field, value in [
            (-1, "error_quality", "bounded"),
            (-1, "symbolic", False),
            (-1, "significant_digits", precision.FORMULA_DIGIT_CAP + 1),
            (0, "error_quality", "estimated"),
        ]:
            altered = copy.deepcopy(update)
            row = next(
                row
                for row in altered["masters"][self.identity]["coefficients"]
                if row["epsilon_power"] == power
            )
            row[field] = value
            if field == "significant_digits":
                row["stored_significant_digits"] = value + 1
            with (
                self.subTest(power=power, field=field),
                self.assertRaisesRegex(ValueError, "invalid numerical precision capability"),
            ):
                precision.coefficients(altered, known)

    def test_formula_evaluation_mutations_are_rejected(self):
        update, rows, receipt = self.formula_fixture()
        key = f"{self.identity}:-1"
        for change, message in [
            (lambda u, r: r["rows"][key].update(significant_digits=9), "selection differs"),
            (lambda u, r: r["rows"][key].update(absolute_error="1e-11"), "selection differs"),
            (lambda u, r: r["rows"][key].update(value_sha256="0" * 64), "selection differs"),
            (lambda u, r: r["exact_rows"].update({self.identity: {}}), "not bound to its exact row"),
            (lambda u, r: (r["rows"][key].update(formula_sha256="0" * 64),
                           r["exact_rows"][self.identity].update({"-1": "0" * 64}),
                           # legacy acceptance, so the publication check is not the one hit
                           u["provenance"].update(accepted_symbolic_commit="f" * 40),
                           u["masters"][self.identity]["accepted_symbolic"].pop("source_publication"),
                           u["masters"][self.identity]["accepted_symbolic"].update(source_commit="f" * 40)),
             "differs from the published exact row"),
            (lambda u, r: r["rows"][key]["previous"].update(value_sha256="0" * 64),
             "does not improve"),
            (lambda u, r: r["rows"][key]["previous"].update(significant_digits=10),
             "does not improve"),
            (lambda u, r: r["rows"][key]["finite_constants"]["vakint::C1"].update(
                value_sha256="0" * 64), "differs from its constants"),
            (lambda u, r: r["rows"][key]["finite_constants"].update(
                {"vakint::Missing": {"significant_digits": 14, "value_sha256": "0" * 64}}),
             "differs from its constants"),
            (lambda u, r: r.update(working_decimal_digits=[20100, 20100]), "unsupported formula"),
            (lambda u, r: r.update(working_decimal_digits=[20000, 20200]), "unsupported formula"),
            (lambda u, r: r.update(error_quality="bounded"), "unsupported formula"),
            (lambda u, r: r.update(accepted=False), "unsupported formula"),
            (lambda u, r: r["rows"][key].update(error_quality="bounded"), "invalid formula evaluation row"),
            (lambda u, r: r["rows"][key].update(master_id="L4_other"), "invalid formula evaluation row"),
            (lambda u, r: r["rows"][key].pop("previous"), "invalid formula evaluation row"),
            (lambda u, r: r["portable_proof_index"].update(sha256="0" * 64), "evidence index checksum"),
        ]:
            altered, receipt_ = copy.deepcopy(update), copy.deepcopy(receipt)
            change(altered, receipt_)
            self.write_formula_receipt(altered, receipt_)
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                self.load_fixture(altered, rows)
        # A stale receipt checksum and a tampered evidence archive are rejected.
        self.write_formula_receipt(update, receipt)
        self.assertEqual(self.load_fixture(update, rows), update)
        altered = copy.deepcopy(update)
        altered["provenance"]["additional_sources"][precision.FORMULA_SOURCE_ID]["receipt"][
            "sha256"
        ] = "0" * 64
        with self.assertRaisesRegex(ValueError, "receipt checksum differs"):
            self.load_fixture(altered, rows)
        (self.root / "validation/formula-evidence.json.gz").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "evidence archive changed"):
            self.load_fixture(update, rows)

    def test_formula_evaluation_must_be_compatible_with_the_replaced_value(self):
        update, rows, receipt = self.formula_fixture()
        # 2.0003 differs from the replaced 1.9999 by 4e-4 > 1e-12 + 2e-4 + 5e-5.
        self.rewrite_value(update, receipt, "2.0003000000")
        with self.assertRaisesRegex(ValueError, "incompatible with the replaced value"):
            self.load_fixture(update, rows)
        # Within the replaced value's own error the new value is accepted.
        self.rewrite_value(update, receipt, "2.0001000000")
        self.assertEqual(self.load_fixture(update, rows), update)
        # A payload edited behind the receipt and the source digest is rejected.
        path = self.root / "4L" / update["masters"][self.identity]["files"]["numerical.json"]["path"]
        edited = data.read_json(path)
        edited[0][1] = "2.0001000001"
        data.write_json(path, edited)
        with self.assertRaisesRegex(ValueError, "value differs from its payload"):
            self.load_fixture(update, rows)

    def test_formula_source_kind_receipt_and_use_are_enforced(self):
        update, rows, receipt = self.formula_fixture()
        reference = update["provenance"]["additional_sources"][precision.FORMULA_SOURCE_ID]
        for altered_reference in [
            {**reference, "kind": precision.PR11_SOURCE_KIND},
            {**reference, "extra": True},
            {"kind": precision.FORMULA_SOURCE_KIND},
        ]:
            altered = copy.deepcopy(update)
            altered["provenance"]["additional_sources"][precision.FORMULA_SOURCE_ID] = (
                altered_reference
            )
            with self.subTest(reference=altered_reference), self.assertRaises(ValueError):
                self.load_fixture(altered, rows)
        unused = copy.deepcopy(update)
        entry = unused["masters"][self.identity]
        entry["coefficients"] = [
            row for row in entry["coefficients"] if row["epsilon_power"] != -1
        ]
        del entry["sources"]["-1"]
        with self.assertRaisesRegex(ValueError, "unused additional"):
            self.load_fixture(unused, rows)

    def test_replaced_files_accept_only_earlier_upgrades_on_the_chain(self):
        update, rows, receipt = self.formula_fixture()
        entry = update["masters"][self.identity]
        # The file replaced by the formula publication: an earlier upgrade that
        # changed only the selected epsilon^0 row of the archived previous file.
        replaced = [[-1, "1.9999"], [0, "1.2500000"], [1, "3.5"], [2, "7"]]
        archive = self.root / "provenance/formula-before/numerical.json"
        data.write_json(archive, replaced)
        binding = {
            "path": entry["files"]["numerical.json"]["path"],
            "sha256": data.digest(archive),
        }
        entry["replaced_files"] = {
            "numerical.json": {**binding, "archive": "provenance/formula-before/numerical.json"}
        }
        data.write_json(self.root / "4L" / precision.LOOP_RECEIPT, update)
        self.assertTrue(
            precision.accepts_producer_binding(binding, self.master, "numerical.json", self.root)
        )
        self.assertFalse(
            precision.accepts_producer_binding(
                {**binding, "sha256": "0" * 64}, self.master, "numerical.json", self.root
            )
        )
        for rows_, message in [
            ([[-1, "1.9999"], [0, "1.2500000"], [1, "3.5"], [2, "8"]], "not an earlier upgrade"),
            ([[-1, "1.9999"], [0, "1.25"], [1, "3.5"], [2, "7"], [3, "1"]], "not an earlier upgrade"),
            ([[-2, "1.9999"], [0, "1.2500000"], [1, "3.5"], [2, "7"]], "not an earlier upgrade"),
        ]:
            data.write_json(archive, rows_)
            entry["replaced_files"]["numerical.json"]["sha256"] = data.digest(archive)
            with self.subTest(rows=rows_), self.assertRaisesRegex(ValueError, message):
                precision.validate_master(update, self.master, self.root)
        data.write_json(archive, replaced)
        entry["replaced_files"]["numerical.json"]["sha256"] = binding["sha256"]
        archive.write_text(archive.read_text() + " ")
        with self.assertRaisesRegex(ValueError, "replaced numerical precision payload changed"):
            precision.validate_master(update, self.master, self.root)
        for invalid in [
            {"numerical.json": {**binding}},
            {"numerical.json": {**binding, "archive": "x", "path": "masters/P7/numerical.json"}},
            {"graph.dot": {**binding, "archive": "x"}},
            [],
        ]:
            entry["replaced_files"] = invalid
            with self.subTest(invalid=invalid), self.assertRaisesRegex(
                ValueError, "invalid replaced numerical precision payload"
            ):
                precision.validate_master(update, self.master, self.root)


class FormulaEvaluationPublicationTests(unittest.TestCase):
    """The published formula-evaluated rows and the manifests agree exactly."""

    def test_estimated_rows_are_exactly_the_formula_evaluated_rows(self):
        update = data.read_json(data.ROOT / precision.RECEIPT)
        reference = update["provenance"]["additional_sources"][precision.FORMULA_SOURCE_ID]
        receipt = data.read_json(data.ROOT / reference["receipt"]["path"])
        selected = set()
        for identity, entry in update["masters"].items():
            for power, source in entry["sources"].items():
                if source.get("source_id") == precision.FORMULA_SOURCE_ID:
                    selected.add(f"{identity}:{power}")
        self.assertEqual(selected, set(receipt["rows"]))
        estimated = set()
        for loops in range(1, 6):
            manifest = data.read_json(data.ROOT / f"{loops}L/manifest.json")
            for master in manifest["masters"]:
                for row in master["coefficients"]:
                    if row.get("error_quality") == "estimated":
                        estimated.add(f"{master['master_id']}:{row['epsilon_power']}")
                        self.assertTrue(row["symbolic"])
                        self.assertLessEqual(
                            row["significant_digits"], precision.FORMULA_DIGIT_CAP
                        )
        self.assertEqual(estimated, selected)
        for key, row in receipt["rows"].items():
            self.assertGreater(
                row["significant_digits"], row["previous"]["significant_digits"]
            )


class ExactSymbolicRewriteTests(unittest.TestCase):
    """A rewrite restates accepted exact rows; the accepted rows stay the authority."""

    def setUp(self):
        PrecisionSupplementTests.setUp(self)
        entry = self.entry = self.update["masters"][self.identity]
        self.relative = entry["files"]["symbolic.json"]["path"]
        self.path = self.root / "4L" / self.relative
        data.write_json(
            self.path, [[-1, "2"], [0, "2*K5Moment(1)/2"], [1, "K5LogMoment(1)"]]
        )
        accepted = self.path.read_text()
        self.previous_sha256 = data.digest(self.path)
        entry["accepted_symbolic"] = {
            "path": self.relative,
            "sha256": self.previous_sha256,
            "contents": accepted,
        }
        for row in entry["coefficients"]:
            row["symbolic"] = True
        self.archive = "provenance/rewrite-before/4L/masters/P6/symbolic.json"
        (self.root / self.archive).parent.mkdir(parents=True, exist_ok=True)
        (self.root / self.archive).write_text(accepted)
        entry["symbolic_rewrite"] = {
            "source_publication": "rewrite-v1",
            "previous": {
                "path": self.relative,
                "sha256": self.previous_sha256,
                "archive": self.archive,
            },
        }
        self.write_rewrite([[-1, "2"], [0, "K5Moment(1)"], [1, "K5LogMoment(1)"]])

    def write_rewrite(self, rows, receipt_rows=None):
        """Write the rewritten payload and a receipt binding it to the preserved rows."""
        data.write_json(self.path, rows)
        checksum = data.digest(self.path)
        self.entry["files"]["symbolic.json"]["sha256"] = checksum
        self.master["files"]["symbolic.json"]["sha256"] = checksum
        before = json.loads((self.root / self.archive).read_text())
        self.receipt = {
            "schema": precision.REWRITE_RECEIPT_SCHEMA,
            "accepted": True,
            "base_commit": "base",
            "rewrites": {
                self.identity: {
                    "path": self.relative,
                    "previous_sha256": self.entry["symbolic_rewrite"]["previous"]["sha256"],
                    "sha256": checksum,
                    "rows": receipt_rows
                    or {
                        str(power): {
                            "previous_sha256": precision.text_digest(old),
                            "sha256": precision.text_digest(new),
                        }
                        for (power, old), (_, new) in zip(before, rows)
                    },
                }
            },
        }
        self.bind_receipt()

    def bind_receipt(self):
        path = self.root / "provenance/rewrite-v1/receipt.json"
        data.write_json(path, self.receipt)
        self.update["provenance"] = {
            "exact_symbolic_rewrites": {
                "rewrite-v1": {
                    "base_commit": "base",
                    "receipt": {
                        "path": "provenance/rewrite-v1/receipt.json",
                        "sha256": data.digest(path),
                    },
                }
            }
        }

    def test_bound_rewrite_keeps_the_accepted_formulas_as_authority(self):
        precision.validate_master(self.update, self.master, self.root)
        update = copy.deepcopy(self.update)
        del update["masters"][self.identity]["symbolic_rewrite"]
        with self.assertRaisesRegex(ValueError, "changed accepted exact"):
            precision.validate_master(update, self.master, self.root)

    def test_rewrite_receipt_and_scope_mutations_are_rejected(self):
        cases = [
            ("receipt changed", lambda u, r: r.update(accepted=True, extra=1)),
            ("unknown exact symbolic rewrite publication",
             lambda u, r: u["masters"][self.identity]["symbolic_rewrite"].update(
                 source_publication="other")),
            ("invalid exact symbolic rewrite",
             lambda u, r: u["masters"][self.identity]["symbolic_rewrite"].update(extra=1)),
            ("invalid exact symbolic rewrite",
             lambda u, r: u["provenance"].pop("exact_symbolic_rewrites")),
        ]
        for message, mutate in cases:
            update, receipt = copy.deepcopy(self.update), copy.deepcopy(self.receipt)
            mutate(update, receipt)
            data.write_json(self.root / "provenance/rewrite-v1/receipt.json", receipt)
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                precision.validate_master(update, self.master, self.root)
        for field, value in [
            ("accepted", False),
            ("schema", "other"),
            ("base_commit", "other"),
        ]:
            self.receipt = {**copy.deepcopy(self.receipt), field: value}
            self.bind_receipt()
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "scope differs"):
                precision.validate_master(self.update, self.master, self.root)
            self.setUp()

    def test_rewritten_rows_must_match_their_receipt_and_preimage(self):
        # A row edited after the rewrite (checksums updated) differs from the receipt.
        rows = [[-1, "2"], [0, "K5Moment(1)"], [1, "K5LogMoment(1)"]]
        receipt_rows = copy.deepcopy(self.receipt["rewrites"][self.identity]["rows"])
        self.write_rewrite(
            [[-1, "2"], [0, "invented_formula"], [1, "K5LogMoment(1)"]], receipt_rows
        )
        with self.assertRaisesRegex(ValueError, "row differs from its receipt"):
            precision.validate_master(self.update, self.master, self.root)
        self.write_rewrite(rows)
        precision.validate_master(self.update, self.master, self.root)
        # The rewrite may not add or drop rows.
        self.write_rewrite(rows[:2])
        with self.assertRaisesRegex(ValueError, "changes epsilon rows"):
            precision.validate_master(self.update, self.master, self.root)
        self.write_rewrite(rows)
        # A changed preserved pre-image is detected by its checksum ...
        archive = self.root / self.archive
        archive.write_text(archive.read_text().replace("2*K5Moment", "3*K5Moment"))
        with self.assertRaisesRegex(ValueError, "pre-rewrite symbolic payload changed"):
            precision.validate_master(self.update, self.master, self.root)
        # ... and a consistently rebound pre-image is not the accepted formula.
        self.entry["symbolic_rewrite"]["previous"]["sha256"] = data.digest(archive)
        self.write_rewrite(rows)
        with self.assertRaisesRegex(ValueError, "changed accepted exact"):
            precision.validate_master(self.update, self.master, self.root)

    def test_rewrite_cannot_change_unselected_or_numerical_only_rows(self):
        archive = self.root / self.archive
        before = json.loads(archive.read_text())
        before[0][1] = "3"
        archive.write_text(json.dumps(before) + "\n")
        self.entry["symbolic_rewrite"]["previous"]["sha256"] = data.digest(archive)
        self.entry["accepted_symbolic"]["contents"] = archive.read_text()
        self.entry["accepted_symbolic"]["sha256"] = data.digest(archive)
        self.write_rewrite([[-1, "3"], [0, "K5Moment(1)"], [1, "K5LogMoment(1)"]])
        with self.assertRaisesRegex(ValueError, "unselected epsilon rows"):
            precision.validate_master(self.update, self.master, self.root)
        self.setUp()
        # A numerical-only row must equal its value before and after the rewrite.
        archive = self.root / self.archive
        self.entry["coefficients"][1]["symbolic"] = False
        archive.write_text(json.dumps([[-1, "2"], [0, "2*K5Moment(1)/2"], [1, "3.5000000"]]) + "\n")
        self.entry["symbolic_rewrite"]["previous"]["sha256"] = data.digest(archive)
        self.entry["accepted_symbolic"]["contents"] = archive.read_text()
        self.entry["accepted_symbolic"]["sha256"] = data.digest(archive)
        self.write_rewrite([[-1, "2"], [0, "K5Moment(1)"], [1, "3.5000000"]])
        precision.validate_master(self.update, self.master, self.root)
        self.write_rewrite([[-1, "2"], [0, "K5Moment(1)"], [1, "7/2"]])
        with self.assertRaisesRegex(ValueError, "differs from accepted source"):
            precision.validate_master(self.update, self.master, self.root)

    def test_published_rewrite_binds_every_supplemented_symbolic_payload(self):
        update = data.read_json(data.ROOT / precision.RECEIPT)
        publications = update["provenance"].get("exact_symbolic_rewrites", {})
        for name, publication in publications.items():
            receipt = data.read_json(data.ROOT / publication["receipt"]["path"])
            bound = {
                identity
                for identity, entry in update["masters"].items()
                if entry.get("symbolic_rewrite", {}).get("source_publication") == name
            }
            self.assertTrue(bound)
            self.assertLessEqual(bound, set(receipt["rewrites"]))
            for identity in bound:
                entry = update["masters"][identity]
                self.assertEqual(
                    receipt["rewrites"][identity]["sha256"],
                    entry["files"]["symbolic.json"]["sha256"],
                )


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
