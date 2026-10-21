#!/usr/bin/env python3
"""Authenticate numerical precision upgrades without rewriting producer history."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation, localcontext
from fractions import Fraction
from pathlib import Path

import data

SCHEMA = "vakint.external-data.numerical-precision-supplement.v1"
RECEIPT = "provenance/numerical-precision-supplement.json"
LOOP_RECEIPT = "numerical-precision-supplement.json"
CAPABILITY_FIELDS = {
    "epsilon_power",
    "symbolic",
    "numerical",
    "significant_digits",
    "stored_significant_digits",
    "absolute_error",
    "error_quality",
}


def text_digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def coefficients(update, known):
    if update is None:
        return {}
    if (
        update.get("schema") != SCHEMA
        or update.get("normalization") != "FMFTandMATAD"
        or not isinstance(update.get("masters"), dict)
    ):
        raise ValueError("unsupported numerical precision supplement")
    result = {}
    for identity, entry in update["masters"].items():
        if identity not in known or not isinstance(entry, dict):
            raise ValueError("unknown numerical precision master")
        master = known[identity]
        if entry.get("loop_count") != master["loop_count"] or entry.get(
            "exact_basis_expression"
        ) != master.get("exact_basis_expression"):
            raise ValueError("numerical precision master identity or basis differs")
        rows = entry.get("coefficients")
        if not isinstance(rows, list) or not rows:
            raise ValueError("numerical precision supplement has no coefficients")
        selected = {}
        for row in rows:
            if not isinstance(row, dict) or set(row) != CAPABILITY_FIELDS:
                raise ValueError("invalid numerical precision capability fields")
            power, digits, stored = (
                row["epsilon_power"],
                row["significant_digits"],
                row["stored_significant_digits"],
            )
            if (
                type(power) is not int
                or type(digits) is not int
                or digits < 1
                or type(stored) is not int
                or stored < digits
                or type(row["symbolic"]) is not bool
                or row["numerical"] is not True
                or row["error_quality"] != "bounded"
            ):
                raise ValueError("invalid numerical precision capability")
            if row["symbolic"] and not entry.get("accepted_symbolic"):
                raise ValueError("exact formulas require an accepted symbolic source")
            try:
                bound = Decimal(row["absolute_error"])
            except (InvalidOperation, TypeError, ValueError) as error:
                raise ValueError(
                    "invalid numerical precision absolute error"
                ) from error
            if (
                not isinstance(row["absolute_error"], str)
                or not bound.is_finite()
                or bound <= 0
            ):
                raise ValueError(
                    "numerical precision needs a positive finite absolute error"
                )
            if power in selected:
                raise ValueError("duplicate numerical precision epsilon power")
            selected[power] = row.copy()
        result[identity] = selected
    return result


def validate_oracle_coverage(root, provenance, archive):
    """Retain the frozen original oracle and require its additive coverage fix."""
    reference = provenance.get("oracle_coverage_addendum")
    if reference is None:
        raise ValueError("Bessel oracle coverage requires the anchor-one addendum")
    manifest_path = data.checked_path(root, reference["path"])
    if data.digest(manifest_path) != reference["sha256"]:
        raise ValueError("Bessel oracle coverage addendum checksum differs")
    manifest = data.read_json(manifest_path)
    if manifest.get("schema") != "vakint.bessel-oracle-coverage-addendum.bundle.v1":
        raise ValueError("unsupported Bessel oracle coverage addendum")
    folder = manifest_path.parent
    for name, expected in manifest["files_sha256"].items():
        if data.digest(data.checked_path(folder, name)) != expected:
            raise ValueError(f"Bessel oracle coverage evidence changed: {name}")
    correction = data.read_json(folder / "coverage-correction.json")
    receipt = data.read_json(folder / "validation.json")
    values = data.read_json(folder / "mathematica-anchor-one.json")
    if (
        correction.get("schema")
        != "vakint.precision-periods.oracle-coverage-correction.v1"
        or correction["original_accepted_validation_sha256"]
        != provenance["validation"]["sha256"]
        or correction["original_constants_sha256"] != provenance["payload"]["sha256"]
        or correction["original_portable_bundle_manifest_sha256"]
        != data.digest(archive / "bundle-manifest.json")
        or correction["original_bundle_unchanged"] is not True
        or correction["correct_required_anchor_count"] != 46
        or correction["originally_checked_required_anchor_count"] != 45
        or correction["supplemental_actual_anchor"] != "1"
        or correction["spare_historical_anchor"] != "15/16"
        or correction["reference_decimal_digits"] != 20400
        or correction["supplemental_source_sha256"]
        != data.digest(folder / "mathematica_anchor_one.wl")
        or correction["supplemental_values_sha256"]
        != data.digest(folder / "mathematica-anchor-one.json")
        or receipt.get("accepted") is not True
        or receipt["supplemental_required_anchor_count"] != 1
        or receipt["coverage_correction_sha256"]
        != data.digest(folder / "coverage-correction.json")
        or receipt["coverage_correction_sha256"] != reference["correction_sha256"]
        or receipt["validator_sha256"] != data.digest(folder / "validate_anchor_one.py")
        or data.digest(folder / "validation.json") != reference["validation_sha256"]
        or values["working_decimal_digits"] != 20400
        or values["numerator"] != 1
        or values["denominator"] != 1
        or len(values["values"]) != 2
        or values["terms"] != 12000
    ):
        raise ValueError(
            "Bessel oracle coverage correction does not bind the accepted payload"
        )
    checks = receipt["checks"]
    if (
        len(checks) != 2
        or {(row["order"], row["argument"]) for row in checks} != {(0, "1"), (1, "1")}
        or any(
            type(row["agreed_decimal_digits_lower_bound"]) is not int
            or row["agreed_decimal_digits_lower_bound"] < 20300
            for row in checks
        )
    ):
        raise ValueError("Bessel anchor-one comparison is incomplete")
    # Derive the actual Taylor centers from the two certified exact partitions.
    # A reported count alone previously concealed one missing and one spare point.
    required = set()
    for label, lower in [("a", Fraction(1)), ("b", Fraction(3, 4))]:
        profile = data.read_json(archive / f"moments20000-{label}-complete.json")
        for index, interval in enumerate(profile["intervals"]):
            upper = (
                Fraction(5, 4)
                if label == "b" and index == 0
                else lower * Fraction(3, 2)
            )
            if isinstance(interval["lower"], list) and (
                Fraction(*interval["lower"]) != lower
                or Fraction(*interval["upper"]) != upper
            ):
                raise ValueError("Bessel exact interval partition differs")
            required.add((lower + upper) / 2)
            lower = upper
    oracle = data.read_json(archive / "mathematica-seeds-v2.json")
    historical = {
        Fraction(row["numerator"], row["denominator"]) for row in oracle["rows"]
    }
    supplemental = Fraction(values["numerator"], values["denominator"])
    if (
        len(required) != 46
        or len(historical) != 46
        or required - historical != {Fraction(1)}
        or historical - required != {Fraction(15, 16)}
        or not required <= historical | {supplemental}
    ):
        raise ValueError(
            "independent oracle does not cover the actual Bessel integration anchors"
        )


def load_source(root=data.ROOT):
    root = Path(root)
    path = root / RECEIPT
    if not path.exists():
        return None
    update = data.read_json(path)
    provenance = update.get("provenance", {})
    checked = {}
    for name in ["payload", "validation", "previous_producer_update"]:
        reference = provenance[name]
        file = data.checked_path(root, reference["path"])
        if data.digest(file) != reference["sha256"]:
            raise ValueError(f"numerical precision provenance changed: {name}")
        checked[name] = data.read_json(file)
    payload, validation = checked["payload"], checked["validation"]
    if (
        payload["validation_sha256"] != provenance["validation"]["sha256"]
        or validation.get("accepted") is not True
        or not all(
            validation.get(key) is True
            for key in [
                "full_gap_free_partitions",
                "complete_infinity_tails",
                "source_pins_unchanged",
                "unique_rounding_cells",
            ]
        )
    ):
        raise ValueError("numerical precision acceptance is incomplete")
    archive = data.checked_path(root, provenance["validation"]["path"]).parent
    for name, expected in validation["artifact_sha256"].items():
        if data.digest(data.checked_path(archive, name)) != expected:
            raise ValueError(f"numerical precision proof changed: {name}")
    oracle = data.read_json(archive / "mathematica-validation.json")
    if (
        oracle["complete"] is not True
        or oracle["bessel_anchor_count"] != 46
        or len(oracle["checks"]) != 98
        or oracle["minimum_agreed_decimal_digits"]
        != min(row["agreed_decimal_digits_lower_bound"] for row in oracle["checks"])
        or oracle["minimum_agreed_decimal_digits"] < 20080
        or oracle["source_sha256"] != data.digest(archive / "mathematica-seeds-v2.json")
        or oracle["validator_sha256"]
        != data.digest(archive / "validate_mathematica.py")
    ):
        raise ValueError("independent numerical precision validation is incomplete")
    validate_oracle_coverage(root, provenance, archive)
    authoritative = {row["symbol"]: row for row in payload["constants"]}
    for entry in update["masters"].values():
        if accepted := entry.get("accepted_symbolic"):
            archived = data.checked_path(root, accepted["archive"])
            if (
                data.digest(archived) != accepted["sha256"]
                or archived.read_text() != accepted["contents"]
                or accepted["source_commit"] != provenance["accepted_symbolic_commit"]
            ):
                raise ValueError("accepted exact symbolic source changed")
        for previous in entry["previous_files"].values():
            archived = data.checked_path(root, previous["archive"])
            if (
                data.digest(archived) != previous["sha256"]
                or archived.read_text() != previous["contents"]
            ):
                raise ValueError("preserved numerical precision payload changed")
        for row in entry["coefficients"]:
            source = entry["sources"][str(row["epsilon_power"])]
            original = authoritative[source["symbol"]]
            if (
                original["master_basis"]
                != entry["exact_basis_expression"].replace("::{}::", "::")
                or original["epsilon_power"] != row["epsilon_power"]
                or original["normalization"] != update["normalization"]
                or original["significant_digits"] != row["significant_digits"]
                or original["stored_significant_digits"]
                != row["stored_significant_digits"]
                or original["validation"]["absolute_error_bound"]
                != row["absolute_error"]
                or text_digest(original["numerical_value"])
                != source["numerical_sha256"]
            ):
                raise ValueError(
                    "numerical precision selection differs from accepted payload"
                )
    return update


def loop_slice(update, loops):
    if update is None:
        return None
    masters = {
        identity: entry
        for identity, entry in update["masters"].items()
        if entry["loop_count"] == loops
    }
    return {**update, "masters": masters} if masters else None


def validate_master(update, master, root=data.ROOT):
    entry = update["masters"][master["master_id"]]
    selected = coefficients(
        {**update, "masters": {master["master_id"]: entry}},
        {master["master_id"]: master},
    )
    selected = selected[master["master_id"]]
    directory = Path(root) / f"{master['loop_count']}L"
    current_rows = {}
    for name in ["numerical.json", "symbolic.json"]:
        previous, current = entry["previous_files"][name], entry["files"][name]
        if (
            previous["path"] != current["path"]
            or current != master["files"][name]
            or text_digest(previous["contents"]) != previous["sha256"]
        ):
            raise ValueError("numerical precision payload binding differs")
        path = data.checked_path(directory, current["path"])
        if data.digest(path) != current["sha256"]:
            raise ValueError("numerical precision payload checksum differs")
        old = json.loads(previous["contents"])
        new = data.read_json(path)
        old_map, new_map = dict(old), dict(new)
        if (
            len(old_map) != len(old)
            or len(new_map) != len(new)
            or old_map.keys() != new_map.keys()
            or not selected.keys() <= new_map.keys()
            or [(p, v) for p, v in old if p not in selected]
            != [(p, v) for p, v in new if p not in selected]
        ):
            raise ValueError(
                "numerical precision upgrade changed unselected epsilon rows"
            )
        current_rows[name] = new_map
    accepted = entry.get("accepted_symbolic")
    if accepted is not None and (
        accepted["path"] != entry["files"]["symbolic.json"]["path"]
        or text_digest(accepted["contents"]) != accepted["sha256"]
        or accepted["sha256"] != entry["files"]["symbolic.json"]["sha256"]
        or dict(json.loads(accepted["contents"])) != current_rows["symbolic.json"]
    ):
        raise ValueError("numerical upgrade changed accepted exact symbolic formulas")
    for power, row in selected.items():
        value = current_rows["numerical.json"][power]
        source = entry["sources"][str(power)]
        if (
            not row["symbolic"] and current_rows["symbolic.json"][power] != value
        ) or text_digest(value) != source["numerical_sha256"]:
            raise ValueError("numerical precision value differs from accepted source")
        with localcontext() as context:
            context.prec = row["stored_significant_digits"] + 50
            number, bound = Decimal(value), Decimal(row["absolute_error"])
            if (
                not number.is_finite()
                or number.is_zero()
                or len(number.as_tuple().digits) != row["stored_significant_digits"]
                or bound >= abs(number) * Decimal(10) ** -row["significant_digits"]
            ):
                raise ValueError("numerical precision value does not satisfy its bound")


def accepts_producer_binding(expected, master, name, root=data.ROOT):
    path = Path(root) / f"{master['loop_count']}L" / LOOP_RECEIPT
    if not path.exists():
        return False
    update = data.read_json(path)
    entry = update.get("masters", {}).get(master["master_id"])
    if entry is None or name not in entry["previous_files"]:
        return False
    previous = entry["previous_files"][name]
    if expected != {key: previous[key] for key in ["path", "sha256"]}:
        return False
    validate_master(update, master, root)
    return True


def validate_loop(directory, masters):
    directory = Path(directory)
    path = directory / LOOP_RECEIPT
    if not path.exists():
        return {}
    update = data.read_json(path)
    known = {master["master_id"]: master for master in masters}
    selected = coefficients(update, known)
    for identity in selected:
        validate_master(update, known[identity], directory.parent)
    return selected


if __name__ == "__main__":
    update = load_source()
    if update is None:
        raise SystemExit("No numerical precision supplement installed")
    known = {
        master["master_id"]: master
        for loops in range(1, 6)
        for master in data.read_json(data.ROOT / f"{loops}L/manifest.json")["masters"]
    }
    for identity, entry in update["masters"].items():
        master = {
            **known[identity],
            "files": {**known[identity]["files"], **entry["files"]},
        }
        validate_master(update, master)
    print(
        f"Verified {len(update['masters'])} numerical precision upgrades and archived proofs"
    )
