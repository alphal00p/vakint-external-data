"""Validate snapshot-local finite periods carried by a loop pack."""

from decimal import Decimal, InvalidOperation, localcontext

import data

RECEIPT = "provenance/finite-constant-bindings.json"


def validate_source(root):
    """Bind the runtime schema projection to immutable independently proved inputs."""
    path = root / RECEIPT
    if not path.exists():
        if any((root / f"{loops}L/constants.json").exists() for loops in range(1, 6)):
            raise ValueError("finite constant source provenance is missing")
        return
    receipt = data.read_json(path)
    if receipt.get("schema") != "vakint.external-data.finite-constant-bindings.v1":
        raise ValueError("unsupported finite constant source provenance")
    records = {}
    for name in ["runtime_payload", "source_payload", "validation", "symbolic_review"]:
        reference = receipt[name]
        file = data.checked_path(root, reference["path"])
        if data.digest(file) != reference["sha256"]:
            raise ValueError(f"finite constant provenance changed: {name}")
        records[name] = data.read_json(file)
    for reference in receipt["bundles"]:
        manifest = data.checked_path(root, reference["path"])
        if data.digest(manifest) != reference["sha256"]:
            raise ValueError("finite constant proof manifest changed")
        contents = data.read_json(manifest)
        hashes = contents.get("files_sha256", contents.get("file_sha256"))
        if not isinstance(hashes, dict) or not hashes:
            raise ValueError("finite constant proof inventory is missing")
        for name, expected in hashes.items():
            if data.digest(data.checked_path(manifest.parent, name)) != expected:
                raise ValueError(f"finite constant proof input changed: {name}")
    validation = records["validation"]
    if (
        validation.get("accepted") is not True
        or validation.get("no_master_alias_inversion") is not True
        or validation["payload_sha256"] != receipt["source_payload"]["sha256"]
    ):
        raise ValueError("finite constant primitive acceptance is incomplete")
    symbolic = records["symbolic_review"]
    if (
        symbolic.get("accepted") is not True
        or symbolic.get("logarithmic_moment_factor") != 3
        or len(symbolic.get("exact_formula_checks", [])) != 24
        or any(row["exact_difference"] for row in symbolic["exact_formula_checks"])
        or len(symbolic.get("numerical_checks", [])) != 8
        or any(
            row["stored_digits_identical"] < 20008
            for row in symbolic["numerical_checks"]
        )
    ):
        raise ValueError("finite constant symbolic definition review is incomplete")
    source = {
        record["symbol"]: record for record in records["source_payload"]["constants"]
    }
    actual = {record["symbol"]: record for record in records["runtime_payload"]}
    additional = receipt.get("additional_sources", {})
    if set(additional) - {"independent-d2-v1", "independent-d2-taylor01-v2"}:
        raise ValueError("unknown finite constant source adapter")
    extra = {}
    previous = actual
    if "independent-d2-taylor01-v2" in additional:
        extra = _validate_d2_taylor01_source(
            root, additional["independent-d2-taylor01-v2"], actual
        )
        previous = {symbol: record for symbol, record in actual.items() if symbol not in extra}
    if "independent-d2-v1" in additional:
        extra.update(_validate_d2_source(root, additional["independent-d2-v1"], previous))
    if (
        len(actual) != len(records["runtime_payload"])
        or set(source) & set(extra)
        or set(source) | set(extra) != set(actual)
    ):
        raise ValueError("finite constant schema projection changes identities")
    for symbol, original in source.items():
        record = actual[symbol]
        if (
            any(
                record[field] != original[field]
                for field in [
                    "value",
                    "significant_digits",
                    "absolute_error",
                    "definition",
                ]
            )
            or record["error_quality"] != original["error_quality"].lower()
            or record["provenance"]["stored_significant_digits"]
            != original["stored_significant_digits"]
            or record["provenance"]["definition_metadata"]
            != original["definition_metadata"]
        ):
            raise ValueError(
                "finite constant schema projection changes accepted values"
            )


def _validate_d2_source(root, reference, actual):
    from d2_constants import derive

    return _validate_d2_projection(
        root,
        reference,
        actual,
        derive,
        "vakint.external-data.independent-d2-runtime-projection.v1",
        {"vakint::PR7D2", "vakint::PR10D2", "vakint::PR15D2"},
    )


def _validate_d2_taylor01_source(root, reference, actual):
    from d2_constants import derive_taylor01

    return _validate_d2_projection(
        root,
        reference,
        actual,
        derive_taylor01,
        "vakint.external-data.independent-d2-taylor01-runtime-projection.v2",
        {"vakint::PR7D2Eps1", "vakint::PR10D2Eps1"},
    )


def _validate_d2_projection(root, reference, actual, derive, schema, symbols):
    path = data.checked_path(root, reference["path"])
    if data.digest(path) != reference["sha256"]:
        raise ValueError("independent D2 projection receipt changed")
    receipt = data.read_json(path)
    if (
        receipt.get("schema") != schema
        or receipt.get("accepted") is not True
        or receipt.get("no_new_numerical_calculation") is not True
        or receipt.get("no_master_coefficient_inversion") is not True
        or receipt.get("all_errors_estimated_not_bounded") is not True
    ):
        raise ValueError("independent D2 projection acceptance is incomplete")
    payload = data.checked_path(root, receipt["source_payload"]["path"])
    if data.digest(payload) != receipt["source_payload"]["sha256"]:
        raise ValueError("independent D2 source projection changed")
    review_ref = receipt["independent_review"]
    review_path = data.checked_path(root, review_ref["path"])
    if (
        data.digest(review_path) != review_ref["sha256"]
        or data.read_json(review_path).get("source_projection_sha256")
        != receipt["source_payload"]["sha256"]
    ):
        raise ValueError("independent D2 exact-arithmetic review changed")
    expected, readset = derive(root)
    if readset != receipt["readset"] or data.read_json(payload) != expected:
        raise ValueError("independent D2 values differ from accepted source projection")
    extra = {record["symbol"]: record for record in expected}
    if set(extra) != symbols:
        raise ValueError("independent D2 projection changes accepted identities")
    if any(actual.get(symbol) != record for symbol, record in extra.items()):
        raise ValueError("independent D2 runtime schema projection differs")
    before = receipt["previous_runtime_payload"]
    previous = data.checked_path(root, before["path"])
    if data.digest(previous) != before["sha256"]:
        raise ValueError("previous finite constants before-image changed")
    old_receipt = receipt["previous_binding_receipt"]
    old_path = data.checked_path(root, old_receipt["path"])
    if (
        data.digest(old_path) != old_receipt["sha256"]
        or data.read_json(old_path)["runtime_payload"]["sha256"] != before["sha256"]
    ):
        raise ValueError("previous finite constant receipt before-image changed")
    previous_records = data.read_json(previous)
    previous_symbols = {record["symbol"] for record in previous_records}
    if previous_symbols != set(actual) - set(extra) or any(
        actual.get(record["symbol"]) != record for record in previous_records
    ):
        raise ValueError("D2 addition changed previous finite constant records")
    return extra


def binding(directory):
    path = directory / "constants.json"
    if not path.exists():
        return None
    records = data.read_json(path)
    if not isinstance(records, list) or not records:
        raise ValueError("finite constant bindings must be a nonempty list")
    symbols = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != {
            "symbol",
            "value",
            "significant_digits",
            "absolute_error",
            "error_quality",
            "definition",
            "provenance",
        }:
            raise ValueError("invalid finite constant binding fields")
        symbol, digits = record["symbol"], record["significant_digits"]
        if (
            not isinstance(symbol, str)
            or not symbol.startswith("vakint::")
            or symbol in symbols
            or type(digits) is not int
            or digits < 1
            or record["error_quality"] not in {"bounded", "estimated"}
            or not isinstance(record["definition"], str)
            or not record["definition"]
            or not isinstance(record["provenance"], dict)
            or not record["provenance"]
            or not isinstance(record["value"], str)
            or not isinstance(record["absolute_error"], str)
        ):
            raise ValueError("invalid finite constant identity or capability")
        try:
            value, error = Decimal(record["value"]), Decimal(record["absolute_error"])
        except InvalidOperation as failure:
            raise ValueError("invalid finite constant decimal") from failure
        with localcontext() as context:
            context.prec = digits + 32
            if (
                not value.is_finite()
                or not error.is_finite()
                or error < 0
                or (value != 0 and error >= abs(value) * Decimal(10) ** -digits)
            ):
                raise ValueError(
                    "finite constant bound does not support its declared digits"
                )
        symbols.add(symbol)
    return {"path": "constants.json", "sha256": data.digest(path)}
