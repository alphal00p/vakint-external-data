#!/usr/bin/env python3
"""Authenticate numerical precision upgrades without rewriting producer history."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from decimal import Decimal, InvalidOperation, localcontext
from fractions import Fraction
from pathlib import Path

import data

SCHEMA = "vakint.external-data.numerical-precision-supplement.v1"
RECEIPT = "provenance/numerical-precision-supplement.json"
LOOP_RECEIPT = "numerical-precision-supplement.json"
PR11_SOURCE_ID = "pr11d-transport-20000"
PR11_SOURCE_KIND = "vakint.pr11d.bounded-transport-20000.v1"
# Independently reviewed final implementation, including the actual production
# chain and scientific read-set trust pins. Bundle metadata cannot replace it.
PR11_VERIFIER_SHA256 = (
    "1cf290b886aeff1a80c34a39daf64f16fb647c89f5e22cc5610126f1bbf31ce7"
)
# Values evaluated from already-published exact rows. The receipt binds every
# value to its exact row text, the replaced value and the finite constants used.
FORMULA_SOURCE_ID = "symbolic-expression-evaluation-v1"
FORMULA_SOURCE_KIND = "vakint.symbolic-expression-evaluation.v1"
FORMULA_RECEIPT_SCHEMA = "vakint.external-data.symbolic-expression-evaluation.v1"
FORMULA_DIGIT_CAP = 20000
FORMULA_ROW_FIELDS = {
    "loop_count",
    "master_id",
    "master_basis",
    "epsilon_power",
    "normalization",
    "formula_sha256",
    "value_sha256",
    "significant_digits",
    "stored_significant_digits",
    "absolute_error",
    "error_quality",
    "finite_constants",
    "previous",
}
ADDITIONAL_SOURCE_IDS = {PR11_SOURCE_ID, FORMULA_SOURCE_ID}
# Exact restatements of published rows (same values, other constants). The
# receipt binds every rewritten row text to its preserved pre-rewrite text.
REWRITE_RECEIPT_SCHEMA = "vakint.external-data.exact-symbolic-rewrite.v1"
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
        sources = entry.get("sources")
        selected = {}
        for row in rows:
            if not isinstance(row, dict) or set(row) != CAPABILITY_FIELDS:
                raise ValueError("invalid numerical precision capability fields")
            power, digits, stored = (
                row["epsilon_power"],
                row["significant_digits"],
                row["stored_significant_digits"],
            )
            source = (
                sources.get(str(power))
                if isinstance(sources, dict) and type(power) is int
                else None
            )
            # Only an evaluation of an exact row is an estimate; every other
            # accepted source remains an interval-bounded finite payload.
            formula = (
                isinstance(source, dict)
                and source.get("source_id") == FORMULA_SOURCE_ID
            )
            if (
                type(power) is not int
                or type(digits) is not int
                or digits < 1
                or type(stored) is not int
                or stored < digits
                or type(row["symbolic"]) is not bool
                or row["numerical"] is not True
                or row["error_quality"] != ("estimated" if formula else "bounded")
                or (
                    formula
                    and (row["symbolic"] is not True or digits > FORMULA_DIGIT_CAP)
                )
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


def _load_bessel_source(root, provenance, payload, validation):
    """Keep the legacy proof and oracle requirements independent of new sources."""
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
    return payload["constants"]


def _pr11_path(root, relative):
    if not isinstance(relative, str) or not relative:
        raise ValueError("invalid PR11 proof path")
    path = data.checked_path(root, relative)
    current = root
    for component in Path(relative).parts:
        current /= component
        if current.is_symlink():
            raise ValueError("PR11 proof paths must not contain symlinks")
    return path


def _pr11_artifact(root, reference):
    if (
        not isinstance(reference, dict)
        or set(reference) not in ({"path", "sha256"}, {"path", "sha256", "bytes"})
        or not isinstance(reference["path"], str)
        or not isinstance(reference["sha256"], str)
        or len(reference["sha256"]) != 64
        or any(c not in "0123456789abcdef" for c in reference["sha256"])
        or (
            "bytes" in reference
            and (type(reference["bytes"]) is not int or reference["bytes"] < 1)
        )
    ):
        raise ValueError("invalid PR11 plaintext artifact descriptor")
    path = _pr11_path(root, reference["path"])
    with path.open("rb") as stream:
        contents = stream.read(16 * 1024 * 1024 + 1)
    if (
        len(contents) > 16 * 1024 * 1024
        or hashlib.sha256(contents).hexdigest() != reference["sha256"]
        or ("bytes" in reference and len(contents) != reference["bytes"])
    ):
        raise ValueError("PR11 plaintext artifact checksum or size differs")
    return path, contents


def _unique_json(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate PR11 JSON key")
        result[key] = value
    return result


def _verify_pr11_bundle(directory, index_name, verifier):
    # Execute the authenticated bytes from a private copy, not a path that could
    # be replaced between its hash check and Python opening it. Isolated mode
    # excludes source-tree imports and Python environment overrides.
    with tempfile.TemporaryDirectory(prefix="vakint-pr11-verifier-") as temporary:
        script = Path(temporary) / "verify_bundle.py"
        script.write_bytes(verifier)
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-B",
                    str(script),
                    str(directory),
                    "--index",
                    index_name,
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=300,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            raise ValueError("PR11 standalone proof verification failed") from error
    return json.loads(result.stdout, object_pairs_hook=_unique_json)


def _load_pr11_source(root, reference):
    """Admit only the sealed finite period through its fixed scientific verifier."""
    if (
        not isinstance(reference, dict)
        or set(reference) != {"kind", "payload", "validation", "proof_manifest"}
        or reference["kind"] != PR11_SOURCE_KIND
    ):
        raise ValueError("invalid additional numerical precision source adapter")
    root = Path(root)
    artifacts = {
        name: _pr11_artifact(root, reference[name])
        for name in ["payload", "validation", "proof_manifest"]
    }
    index_path, index_bytes = artifacts["proof_manifest"]
    directory = index_path.parent
    index = json.loads(index_bytes, object_pairs_hook=_unique_json)
    if index.get("schema") != "vakint.pr11d.portable-proof-index.v1":
        raise ValueError("unsupported PR11 proof index")
    for name in ["payload", "validation"]:
        indexed = index["artifacts"][name]
        path, contents = _pr11_artifact(directory, indexed)
        if path != artifacts[name][0] or contents != artifacts[name][1]:
            raise ValueError("PR11 outer artifact differs from proof index")
    implementation = index["implementations"]["verify_bundle"]
    if implementation["sha256"] != PR11_VERIFIER_SHA256:
        raise ValueError(
            "PR11 verifier is not the independently accepted implementation"
        )
    _, verifier = _pr11_artifact(directory, implementation)
    for descriptors in [index["files"], index["artifacts"], index["implementations"]]:
        for descriptor in descriptors.values():
            _pr11_path(directory, descriptor["path"])
    # The fixed verifier authenticates all stored and decoded proof bytes and
    # replays both final interval convolutions, rounding, physical identities,
    # normalization and the complete typed scientific read-set. Gzip descriptor
    # sha256 fields identify decoded content, not compressed bytes.
    verified = _verify_pr11_bundle(directory, index_path.name, verifier)
    if (
        verified.get("schema") != "vakint.pr11d.portable-bundle-verification.v1"
        or verified.get("accepted") is not True
        or verified.get("payload_sha256") != reference["payload"]["sha256"]
        or verified.get("provenance_manifest_sha256")
        != index["artifacts"]["provenance_manifest"]["sha256"]
        or verified.get("validated_significant_digits") != 20000
        or verified.get("stored_significant_digits") != 20008
        or verified.get("two_refinement_interval_convolutions_replayed") is not True
        or verified.get("complete_independent_DE_validation") is not False
        or verified.get("AMFlow_20000_digit_comparison_claimed") is not False
        or verified.get("native_or_Mathematica_execution") is not False
    ):
        raise ValueError("PR11 scientific verification result differs")
    for name, (path, contents) in artifacts.items():
        if _pr11_artifact(root, reference[name]) != (path, contents):
            raise ValueError("PR11 artifact changed during verification")
    payload = json.loads(artifacts["payload"][1], object_pairs_hook=_unique_json)
    if payload.get("schema") != "vakint.pr11d.validated-periods.v1" or set(
        payload.get("constants", {})
    ) != {"PR11dep0"}:
        raise ValueError("unsupported PR11 finite-period payload")
    row = payload["constants"]["PR11dep0"]
    if (
        row["symbol"] != "PR11dep0"
        or row["master_basis"] != "vakint::PR11d"
        or type(row["epsilon_power"]) is not int
        or row["epsilon_power"] != 0
        or row["normalization"] != "FMFT"
        or row["unit_mass_squared"] != "1"
        or row["error_quality"] != "rigorous-bound"
        or row["Minkowski_overall_sign"] != -1
        or row["validated_significant_digits"] != 20000
        or row["stored_significant_digits"] != 20008
        or any(type(power) is not int for power in row["ordered_powers"])
    ):
        raise ValueError("PR11 finite-period scope differs")
    masters = data.read_json(root / "4L/manifest.json")["masters"]
    target = [master for master in masters if master["master_id"] == row["master_id"]]
    if (
        len(target) != 1
        or target[0]["family_sha256"] != row["family_sha256"]
        or target[0]["powers"] != row["ordered_powers"]
        or target[0]["exact_basis_expression"] != "vakint::{}::PR11d"
    ):
        raise ValueError("PR11 physical target is not an existing direct period alias")
    if not isinstance(row["value"], str) or not row["value"]:
        raise ValueError("PR11 published center must be a decimal string")
    number = Decimal(row["value"])
    stored = len(number.as_tuple().digits)
    if (
        not number.is_finite()
        or number.is_zero()
        or stored != row["stored_significant_digits"]
    ):
        raise ValueError("PR11 published center has inconsistent stored precision")
    # Finiteness authenticates FMFT/native equality only at epsilon zero. The
    # published center already includes the single Wick sign; never apply it again.
    return [
        {
            "symbol": row["symbol"],
            "master_basis": row["master_basis"],
            "epsilon_power": 0,
            "normalization": "FMFTandMATAD",
            "significant_digits": row["validated_significant_digits"],
            "stored_significant_digits": stored,
            "numerical_value": row["value"],
            "validation": {"absolute_error_bound": row["absolute_error_upper_bound"]},
        }
    ]


def _hex_digest(value):
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value)
    )


def _formula_portable_index(root, reference):
    """Authenticate the archived evaluation evidence named by the receipt."""
    if (
        not isinstance(reference, dict)
        or set(reference) != {"path", "sha256"}
        or not _hex_digest(reference["sha256"])
    ):
        raise ValueError("invalid formula evaluation evidence index")
    path = data.checked_path(root, reference["path"])
    if data.digest(path) != reference["sha256"]:
        raise ValueError("formula evaluation evidence index checksum differs")
    index = json.loads(path.read_text(), object_pairs_hook=_unique_json)
    archives = index.get("archives")
    if (
        index.get("schema")
        != "vakint.external-data.portable-producer-evidence-index.v1"
        or not isinstance(archives, list)
        or not archives
    ):
        raise ValueError("unsupported formula evaluation evidence index")
    for item in archives:
        portable = item.get("portable_archive") if isinstance(item, dict) else None
        if not isinstance(portable, dict) or not _hex_digest(portable.get("sha256")):
            raise ValueError("invalid formula evaluation evidence archive")
        archive = data.checked_path(root, portable["path"])
        if data.file_record(archive) != {
            "sha256": portable["sha256"],
            "bytes": portable["bytes"],
        }:
            raise ValueError("formula evaluation evidence archive changed")


def _load_formula_source(root, reference):
    """Admit values evaluated from published exact rows; never new exactness."""
    if (
        not isinstance(reference, dict)
        or set(reference) != {"kind", "receipt"}
        or reference["kind"] != FORMULA_SOURCE_KIND
        or not isinstance(reference["receipt"], dict)
        or set(reference["receipt"]) != {"path", "sha256"}
    ):
        raise ValueError("invalid additional numerical precision source adapter")
    root = Path(root)
    path = data.checked_path(root, reference["receipt"]["path"])
    if data.digest(path) != reference["receipt"]["sha256"]:
        raise ValueError("formula evaluation receipt checksum differs")
    receipt = json.loads(path.read_text(), object_pairs_hook=_unique_json)
    working = receipt.get("working_decimal_digits")
    if (
        receipt.get("schema") != FORMULA_RECEIPT_SCHEMA
        or receipt.get("accepted") is not True
        or receipt.get("error_quality") != "estimated"
        or receipt.get("digit_cap") != FORMULA_DIGIT_CAP
        or not isinstance(receipt.get("base_commit"), str)
        or len(receipt["base_commit"]) != 40
        or not isinstance(working, list)
        or len(working) != 2
        or any(type(digits) is not int for digits in working)
        or working[0] == working[1]
        or min(working) <= FORMULA_DIGIT_CAP
        or not isinstance(receipt.get("rows"), dict)
        or not receipt["rows"]
        or not isinstance(receipt.get("exact_rows"), dict)
    ):
        raise ValueError("unsupported formula evaluation receipt")
    _formula_portable_index(root, receipt.get("portable_proof_index"))
    result = []
    for key, row in receipt["rows"].items():
        if not isinstance(row, dict) or not FORMULA_ROW_FIELDS <= set(row):
            raise ValueError("invalid formula evaluation row")
        identity, power = row["master_id"], row["epsilon_power"]
        if (
            type(power) is not int
            or key != f"{identity}:{power}"
            or row["normalization"] != "FMFTandMATAD"
            or row["error_quality"] != "estimated"
            or not _hex_digest(row["formula_sha256"])
            or not _hex_digest(row["value_sha256"])
            or not isinstance(row["finite_constants"], dict)
            or not isinstance(row["previous"], dict)
        ):
            raise ValueError("invalid formula evaluation row")
        # The receipt itself binds the exact row text of every evaluation.
        bound = receipt["exact_rows"].get(identity)
        if (
            not isinstance(bound, dict)
            or bound.get(str(power)) != row["formula_sha256"]
        ):
            raise ValueError("formula evaluation is not bound to its exact row")
        result.append(
            {
                "symbol": key,
                "master_basis": row["master_basis"],
                "epsilon_power": power,
                "normalization": row["normalization"],
                "significant_digits": row["significant_digits"],
                "stored_significant_digits": row["stored_significant_digits"],
                "numerical_sha256": row["value_sha256"],
                "validation": {"absolute_error_bound": row["absolute_error"]},
                "evaluation": row,
            }
        )
    return result


def _finite_constant_values(root, authoritative):
    """Published finite constants that an evaluated formula may contain."""
    constants = {}
    path = Path(root) / "4L/constants.json"
    if path.exists():
        for record in data.read_json(path):
            constants[record["symbol"]] = (
                record["significant_digits"],
                text_digest(record["value"]),
            )
    for (source_id, symbol), row in authoritative.items():
        if source_id == FORMULA_SOURCE_ID or "numerical_value" not in row:
            continue
        name = symbol if symbol.startswith("vakint::") else f"vakint::{symbol}"
        constants[name] = (
            row["significant_digits"],
            text_digest(row["numerical_value"]),
        )
    return constants


def _check_formula_evaluation(root, identity, entry, row, original, constants):
    """Bind an evaluated value to its exact row, constants and replaced value."""
    evaluation, power = original["evaluation"], row["epsilon_power"]
    if (
        evaluation["master_id"] != identity
        or evaluation["loop_count"] != entry.get("loop_count")
        or row["symbolic"] is not True
        or row["error_quality"] != "estimated"
    ):
        raise ValueError("formula evaluation master or capability differs")
    accepted = entry.get("accepted_symbolic")
    exact = dict(json.loads(accepted["contents"])) if accepted else {}
    if power not in exact or text_digest(exact[power]) != evaluation["formula_sha256"]:
        raise ValueError("formula evaluation differs from the published exact row")
    for symbol, used in evaluation["finite_constants"].items():
        current = constants.get(symbol)
        if (
            not isinstance(used, dict)
            or current is None
            or (used.get("significant_digits"), used.get("value_sha256")) != current
            or row["significant_digits"] > current[0]
        ):
            raise ValueError("formula evaluation exceeds or differs from its constants")
    before = evaluation["previous"]
    previous = dict(json.loads(entry["previous_files"]["numerical.json"]["contents"]))
    old_digits = before.get("significant_digits")
    if (
        power not in previous
        or text_digest(previous[power]) != before.get("value_sha256")
        or type(old_digits) is not int
        or old_digits < 1
        or row["significant_digits"] <= old_digits
    ):
        raise ValueError("formula evaluation does not improve the replaced value")
    directory = Path(root) / f"{entry['loop_count']}L"
    current = dict(
        data.read_json(
            data.checked_path(directory, entry["files"]["numerical.json"]["path"])
        )
    )
    value = current.get(power)
    if not isinstance(value, str) or text_digest(value) != original["numerical_sha256"]:
        raise ValueError("formula evaluation value differs from its payload")
    with localcontext() as context:
        context.prec = max(len(value), len(previous[power])) + 50
        new, old = Decimal(value), Decimal(previous[power])
        old_error = (
            Decimal(before["absolute_error"])
            if before.get("absolute_error") is not None
            else abs(old) * Decimal(10) ** -old_digits
        )
        # The replaced string is only correct to half a unit of its last digit.
        storage = Decimal(5).scaleb(old.as_tuple().exponent - 1)
        if (
            not old.is_finite()
            or old.is_zero()
            or abs(new - old) > Decimal(row["absolute_error"]) + old_error + storage
        ):
            raise ValueError(
                "formula evaluation is incompatible with the replaced value"
            )


def _index_source_rows(source_id, rows):
    authoritative = {}
    for row in rows:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("symbol"), str)
            or not row["symbol"]
        ):
            raise ValueError("invalid authoritative numerical precision source row")
        key = source_id, row["symbol"]
        if key in authoritative:
            raise ValueError("duplicate authoritative numerical precision source row")
        authoritative[key] = row
    return authoritative


def _source_key(source, additional):
    if (
        not isinstance(source, dict)
        or set(source)
        not in (
            {"symbol", "numerical_sha256"},
            {"source_id", "symbol", "numerical_sha256"},
        )
        or not isinstance(source.get("symbol"), str)
        or not source["symbol"]
    ):
        raise ValueError("invalid numerical precision source selection")
    source_id = None
    if "source_id" in source:
        source_id = source["source_id"]
        if not isinstance(source_id, str) or source_id not in additional:
            raise ValueError("unknown numerical precision source id")
    return source_id, source["symbol"]


def _published_symbolic_rows(root, publications, identity, accepted):
    """Authenticate exact rows accepted by a later publication receipt."""
    publication = publications.get(accepted["source_publication"])
    if (
        not isinstance(publication, dict)
        or set(publication) != {"base_commit", "receipt"}
        or accepted["source_commit"] != publication["base_commit"]
    ):
        raise ValueError("accepted exact symbolic publication differs")
    path = data.checked_path(root, publication["receipt"]["path"])
    if data.digest(path) != publication["receipt"]["sha256"]:
        raise ValueError("accepted exact symbolic publication receipt changed")
    receipt = data.read_json(path)
    rows = receipt.get("exact_rows", {}).get(identity)
    if (
        receipt.get("base_commit") != publication["base_commit"]
        or receipt.get("accepted") is not True
        or not isinstance(rows, dict)
        or not rows
    ):
        raise ValueError("accepted exact symbolic publication scope differs")
    contents = dict(json.loads(accepted["contents"]))
    powers = set()
    for power, digest in rows.items():
        power = int(power)
        if power not in contents or text_digest(contents[power]) != digest:
            raise ValueError("accepted exact symbolic row differs from its publication")
        powers.add(power)
    return powers


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
    authoritative = _index_source_rows(
        None,
        _load_bessel_source(
            root, provenance, checked["payload"], checked["validation"]
        ),
    )
    additional = provenance.get("additional_sources", {})
    if not isinstance(additional, dict) or additional.keys() - ADDITIONAL_SOURCE_IDS:
        raise ValueError("invalid or unknown additional numerical precision source")
    used = set()
    for entry in update["masters"].values():
        for row in entry["coefficients"]:
            source = entry["sources"][str(row["epsilon_power"])]
            used.add(_source_key(source, additional)[0])
    if additional.keys() - used:
        raise ValueError("unused additional numerical precision source")
    for source_id, reference in additional.items():
        # This fixed dispatch has two reserved additional sources. Source text
        # cannot select imports, callbacks, or a fallback to the Bessel rows.
        loader = (
            _load_pr11_source if source_id == PR11_SOURCE_ID else _load_formula_source
        )
        authoritative.update(_index_source_rows(source_id, loader(root, reference)))
    constants = (
        _finite_constant_values(root, authoritative)
        if FORMULA_SOURCE_ID in additional
        else {}
    )
    publications = provenance.get("accepted_symbolic_publications", {})
    if not isinstance(publications, dict):
        raise ValueError("invalid accepted exact symbolic publications")
    for identity, entry in update["masters"].items():
        published = set()
        if accepted := entry.get("accepted_symbolic"):
            archived = data.checked_path(root, accepted["archive"])
            if (
                data.digest(archived) != accepted["sha256"]
                or archived.read_text() != accepted["contents"]
            ):
                raise ValueError("accepted exact symbolic source changed")
            if "source_publication" in accepted:
                # A later publication may supply exact rows for a precision-
                # supplemented master; its own receipt binds every row text.
                published = _published_symbolic_rows(
                    root, publications, identity, accepted
                )
            elif accepted["source_commit"] != provenance["accepted_symbolic_commit"]:
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
            key = _source_key(source, additional)
            if key not in authoritative:
                raise ValueError("unknown authoritative numerical precision symbol")
            # The finite period never promotes exactness by itself. Only an
            # independently accepted exact row, bound by its publication
            # receipt, may be declared symbolic beside the numerical value.
            if (
                key[0] == PR11_SOURCE_ID
                and row["symbolic"] is not False
                and row["epsilon_power"] not in published
            ):
                raise ValueError("PR11 finite-period precision remains numerical-only")
            original = authoritative[key]
            # Formula evaluations bind their value by digest; the value itself
            # is published once, in the master's numerical payload.
            value_digest = (
                original["numerical_sha256"]
                if key[0] == FORMULA_SOURCE_ID
                else text_digest(original["numerical_value"])
            )
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
                or value_digest != source["numerical_sha256"]
            ):
                raise ValueError(
                    "numerical precision selection differs from accepted payload"
                )
            if key[0] == FORMULA_SOURCE_ID:
                _check_formula_evaluation(
                    root, identity, entry, row, original, constants
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


def _symbolic_rewrite(update, identity, entry, current, root):
    """Authenticate an exact rewrite of a supplemented symbolic payload.

    A later publication may restate every exact row in other constants (for
    example an independent constant basis) without changing its value. The
    accepted formulas, previous files and formula evaluations above remain the
    authority: the rewrite receipt binds each current row text to the row text
    of the preserved pre-rewrite payload, which is returned for those checks.
    """
    rewrite = entry.get("symbolic_rewrite")
    if rewrite is None:
        return None
    publications = update.get("provenance", {}).get("exact_symbolic_rewrites")
    if (
        not isinstance(rewrite, dict)
        or set(rewrite) != {"source_publication", "previous"}
        or not isinstance(publications, dict)
    ):
        raise ValueError("invalid exact symbolic rewrite")
    publication = publications.get(rewrite["source_publication"])
    if not isinstance(publication, dict) or set(publication) != {
        "base_commit",
        "receipt",
    }:
        raise ValueError("unknown exact symbolic rewrite publication")
    path = data.checked_path(Path(root), publication["receipt"]["path"])
    if data.digest(path) != publication["receipt"]["sha256"]:
        raise ValueError("exact symbolic rewrite receipt changed")
    receipt = data.read_json(path)
    rewrites = receipt.get("rewrites")
    bound = rewrites.get(identity) if isinstance(rewrites, dict) else None
    previous = rewrite["previous"]
    if (
        receipt.get("schema") != REWRITE_RECEIPT_SCHEMA
        or receipt.get("accepted") is not True
        or receipt.get("base_commit") != publication["base_commit"]
        or not isinstance(bound, dict)
        or not isinstance(previous, dict)
        or set(previous) != {"path", "sha256", "archive"}
        or previous["path"] != entry["files"]["symbolic.json"]["path"]
        or bound.get("path") != previous["path"]
        or bound.get("previous_sha256") != previous["sha256"]
        or bound.get("sha256") != entry["files"]["symbolic.json"]["sha256"]
    ):
        raise ValueError("exact symbolic rewrite scope differs")
    archived = data.checked_path(Path(root), previous["archive"])
    if data.digest(archived) != previous["sha256"]:
        raise ValueError("preserved pre-rewrite symbolic payload changed")
    old = json.loads(archived.read_text())
    rows = bound.get("rows")
    if (
        not isinstance(rows, dict)
        or [power for power, _ in old] != [power for power, _ in current]
        or len(dict(old)) != len(old)
        or set(rows) != {str(power) for power, _ in old}
    ):
        raise ValueError("exact symbolic rewrite changes epsilon rows")
    for (power, before), (_, after) in zip(old, current):
        row = rows[str(power)]
        if (
            not isinstance(row, dict)
            or row.get("previous_sha256") != text_digest(before)
            or row.get("sha256") != text_digest(after)
        ):
            raise ValueError("exact symbolic rewrite row differs from its receipt")
    return old


def validate_master(update, master, root=data.ROOT):
    entry = update["masters"][master["master_id"]]
    selected = coefficients(
        {**update, "masters": {master["master_id"]: entry}},
        {master["master_id"]: master},
    )
    selected = selected[master["master_id"]]
    directory = Path(root) / f"{master['loop_count']}L"
    current_rows = {}
    rewritten = None
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
        if name == "symbolic.json":
            preimage = _symbolic_rewrite(update, master["master_id"], entry, new, root)
            if preimage is not None:
                # The checks below apply to the authenticated pre-rewrite rows.
                rewritten, new = dict(new), preimage
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
    # A later publication may supersede a payload that an earlier supplement
    # or producer binding already references. Its archived replaced file must
    # agree with the current payload on every unselected row.
    replaced_files = entry.get("replaced_files", {})
    if not isinstance(replaced_files, dict) or replaced_files.keys() - current_rows:
        raise ValueError("invalid replaced numerical precision payload")
    for name, replaced in replaced_files.items():
        if (
            not isinstance(replaced, dict)
            or set(replaced) != {"path", "sha256", "archive"}
            or replaced["path"] != entry["files"][name]["path"]
        ):
            raise ValueError("invalid replaced numerical precision payload")
        archived = data.checked_path(Path(root), replaced["archive"])
        if data.digest(archived) != replaced["sha256"]:
            raise ValueError("replaced numerical precision payload changed")
        rows = json.loads(archived.read_text())
        mapping = dict(rows)
        if (
            len(mapping) != len(rows)
            or mapping.keys() != current_rows[name].keys()
            or any(
                mapping[power] != current_rows[name][power]
                for power in mapping
                if power not in selected
            )
        ):
            raise ValueError(
                "replaced numerical precision payload is not an earlier upgrade"
            )
    accepted = entry.get("accepted_symbolic")
    symbolic_sha256 = (
        entry["files"]["symbolic.json"]["sha256"]
        if rewritten is None
        else entry["symbolic_rewrite"]["previous"]["sha256"]
    )
    if accepted is not None and (
        accepted["path"] != entry["files"]["symbolic.json"]["path"]
        or text_digest(accepted["contents"]) != accepted["sha256"]
        or accepted["sha256"] != symbolic_sha256
        or dict(json.loads(accepted["contents"])) != current_rows["symbolic.json"]
    ):
        raise ValueError("numerical upgrade changed accepted exact symbolic formulas")
    for power, row in selected.items():
        value = current_rows["numerical.json"][power]
        source = entry["sources"][str(power)]
        # A numerical-only row must stay its numerical value, also after a rewrite.
        texts = [current_rows["symbolic.json"][power]]
        if rewritten is not None:
            texts.append(rewritten[power])
        if (
            not row["symbolic"] and any(text != value for text in texts)
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
    replaced = entry.get("replaced_files", {}).get(name)
    bindings = [
        {key: record.get(key) for key in ["path", "sha256"]}
        for record in [previous, replaced]
        if isinstance(record, dict)
    ]
    if expected not in bindings:
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
