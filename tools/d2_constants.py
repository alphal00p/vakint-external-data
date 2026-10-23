"""Derive finite D2 bindings from accepted independent producer receipts.

This is a schema projection of existing data, not a new numerical calculation.
No D4 master coefficient is read. The estimates remain empirical.
"""

import argparse
import gzip
import hashlib
import io
import json
from decimal import Decimal, localcontext
from pathlib import Path

import data


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def reference(root, path):
    return {
        "path": str(path),
        "sha256": digest(data.checked_path(root, path).read_bytes()),
    }


def archive(root, index, expected):
    entries = [
        e for e in index["archives"] if e["original_source"]["sha256"] == expected
    ]
    if not (len(entries) == 1):
        raise ValueError("independent D2 source acceptance or projection differs")
    entry = entries[0]["portable_archive"]
    compressed = data.checked_path(root, entry["path"]).read_bytes()
    if not (
        len(compressed) == entry["bytes"] and digest(compressed) == entry["sha256"]
    ):
        raise ValueError("independent D2 source acceptance or projection differs")
    if not 0 < entry["uncompressed_bytes"] <= 16 * 1024 * 1024:
        raise ValueError("D2 proof object exceeds the schema-projection input limit")
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        decoded = stream.read(entry["uncompressed_bytes"] + 1)
    if not (len(decoded) == entry["uncompressed_bytes"]):
        raise ValueError("independent D2 source acceptance or projection differs")
    if not (digest(decoded) == entry["uncompressed_sha256"] == expected):
        raise ValueError("independent D2 source acceptance or projection differs")
    return json.loads(decoded), entry


def scaled(item):
    return Decimal(item["integer"]) * Decimal(10) ** item["power10"]


def rounded_significant(value, digits):
    return value.quantize(Decimal(10) ** (value.adjusted() - digits + 1))


def derive(root):
    """Reproduce the accepted source projection without a numerical engine."""
    with localcontext() as context:
        # The authenticated decimal sources contain at most 550 significant
        # digits. This retains exact arithmetic for their decimal envelopes.
        context.prec = 2000
        return _derive(root)


def _derive(root):
    readset = []
    records = []
    for family in ["PR7-v23", "PR10-PR15-v24"]:
        index_path = f"provenance/{family}/portable-proof-index.json"
        index = json.loads(data.checked_path(root, index_path).read_bytes())
        readset.append(reference(root, index_path))
        if family == "PR7-v23":
            definition_path = "4L/provenance/PR7-v23/independent-D2-period.json"
            definition = json.loads(
                data.checked_path(root, definition_path).read_bytes()
            )
            if not (
                definition["validation_provenance"]["portable_proof_index"]
                == reference(root, index_path)
            ):
                raise ValueError(
                    "independent D2 source acceptance or projection differs"
                )
            accepted, accepted_ref = archive(
                root,
                index,
                definition["validation_provenance"]["period_Root_acceptance_sha256"],
            )
            validation, validation_ref = archive(
                root, index, accepted["validation"]["sha256"]
            )
            if not (accepted["accepted_actual_independently_defined_D2_auxiliary215"]):
                raise ValueError(
                    "independent D2 source acceptance or projection differs"
                )
            if not (accepted["empirical_not_interval_proof"]):
                raise ValueError(
                    "independent D2 source acceptance or projection differs"
                )
            if not (
                accepted["accepted_auxiliary_digits"]
                == validation["auxiliary_digits"]
                == 215
            ):
                raise ValueError(
                    "independent D2 source acceptance or projection differs"
                )
            if not (
                accepted["strict215_rounding_cell"] == validation["P215_rounding_cell"]
            ):
                raise ValueError(
                    "independent D2 source acceptance or projection differs"
                )
            if not (
                accepted["combined_empirical_model_abs"]
                == validation["combined_empirical_model_abs"]
            ):
                raise ValueError(
                    "independent D2 source acceptance or projection differs"
                )
            profile, profile_ref = archive(
                root, index, accepted["profiles"][1]["sha256"]
            )
            center = Decimal(profile["endpoint_periods"][0][0])
            if not (Decimal(profile["endpoint_periods"][0][1]) == 0):
                raise ValueError(
                    "independent D2 source acceptance or projection differs"
                )
            if not (profile["endpoint_periods"][0] == profile["endpoint_periods"][1]):
                raise ValueError(
                    "independent D2 source acceptance or projection differs"
                )
            if not (
                rounded_significant(center, 215)
                == Decimal(accepted["strict215_rounding_cell"])
            ):
                raise ValueError(
                    "independent D2 source acceptance or projection differs"
                )
            estimate = Decimal(accepted["combined_empirical_model_abs"])
            records.append(
                {
                    "symbol": definition["symbol"],
                    "value": str(center),
                    "significant_digits": 215,
                    "absolute_error": str(estimate),
                    "error_quality": "estimated",
                    "definition": definition["Bessel_integral_definition"],
                    "provenance": {
                        "source_kind": "independent convergent D2 integral; no master coefficient inversion",
                        "error_authority": "accepted two-profile empirical refinement; not an interval certificate",
                        "definition_metadata": definition["mathematical_definition"],
                        "definition": reference(root, definition_path),
                        "portable_proof_index": reference(root, index_path),
                        "acceptance": accepted_ref,
                        "validation": validation_ref,
                        "center_profile": profile_ref,
                        "center_json_pointer": "/endpoint_periods/0/0",
                        "error_json_pointer": "/combined_empirical_model_abs",
                        "independent_Bessel_check_digits": 50,
                        "accepted_significant_digits": 215,
                        "stored_digits_do_not_extend_source_cap": True,
                    },
                }
            )
        else:
            definition_path = (
                "4L/provenance/PR10-PR15-v24/independent-D2-periods-v1.json"
            )
            definition = json.loads(
                data.checked_path(root, definition_path).read_bytes()
            )
            if not (
                definition["portable_validation_proof_index"]
                == reference(root, index_path)
            ):
                raise ValueError(
                    "independent D2 source acceptance or projection differs"
                )
            for position, period in enumerate(definition["periods"]):
                evidence = period["current_independent_auxiliary_evidence"]
                if not (evidence["accepted_significant_digits"] == 215):
                    raise ValueError(
                        "independent D2 source acceptance or projection differs"
                    )
                if not (evidence["empirical_not_interval_proof"]):
                    raise ValueError(
                        "independent D2 source acceptance or projection differs"
                    )
                accepted, accepted_ref = archive(
                    root, index, evidence["Root_adoption"]["sha256"]
                )
                validation, validation_ref = archive(
                    root, index, evidence["validation"]["sha256"]
                )
                if not (accepted["accepted_auxiliary_digits"] == 215):
                    raise ValueError(
                        "independent D2 source acceptance or projection differs"
                    )
                if not (
                    accepted["accepted_actual_independently_defined_E10_E15_at215"]
                ):
                    raise ValueError(
                        "independent D2 source acceptance or projection differs"
                    )
                if not (accepted["empirical_not_interval_proof"]):
                    raise ValueError(
                        "independent D2 source acceptance or projection differs"
                    )
                if accepted["unknown_target_finite_values_used"]:
                    raise ValueError(
                        "independent D2 source acceptance or projection differs"
                    )
                if not (accepted["validation"] == evidence["validation"]):
                    raise ValueError(
                        "independent D2 source acceptance or projection differs"
                    )
                if not (validation["auxiliary_digits"] == 215):
                    raise ValueError(
                        "independent D2 source acceptance or projection differs"
                    )
                if not (
                    validation["two_fresh_full_seed_and_sensitivity_profiles_passed"]
                ):
                    raise ValueError(
                        "independent D2 source acceptance or projection differs"
                    )
                if not (validation["empirical_not_interval_proof"]):
                    raise ValueError(
                        "independent D2 source acceptance or projection differs"
                    )
                profiles = evidence["qualified_bindings"]
                identity = profiles[0]["id"]
                if not (
                    profiles
                    == [
                        p for p in accepted["qualified_bindings"] if p["id"] == identity
                    ]
                ):
                    raise ValueError(
                        "independent D2 source acceptance or projection differs"
                    )
                if not (
                    accepted["strict215_rounding_cells"][identity]
                    == evidence["strict215_rounded_value"]
                ):
                    raise ValueError(
                        "independent D2 source acceptance or projection differs"
                    )
                if not (
                    validation["strict215_rounding_cells"][identity]
                    == evidence["strict215_rounded_value"]
                ):
                    raise ValueError(
                        "independent D2 source acceptance or projection differs"
                    )
                if not (len(profiles) == 2):
                    raise ValueError(
                        "independent D2 source acceptance or projection differs"
                    )
                for profile in profiles:
                    if not (profile["available_significant_source_cap"] == 215):
                        raise ValueError(
                            "independent D2 source acceptance or projection differs"
                        )
                    raw_profile, _ = archive(root, index, profile["source"]["sha256"])
                    if raw_profile["target_or_expected_E10_E15_or_D4_value_used"]:
                        raise ValueError(
                            "independent D2 source acceptance or projection differs"
                        )
                    if not (raw_profile["empirical_not_interval_proof"]):
                        raise ValueError(
                            "independent D2 source acceptance or projection differs"
                        )
                    if not (
                        raw_profile["endpoint_periods"][0]
                        == raw_profile["endpoint_periods"][1]
                    ):
                        raise ValueError(
                            "independent D2 source acceptance or projection differs"
                        )
                    endpoint = raw_profile["endpoint_periods"][0][position]
                    if not (Decimal(endpoint[0]) == scaled(profile["center"])):
                        raise ValueError(
                            "independent D2 source acceptance or projection differs"
                        )
                    if not (Decimal(endpoint[1]) == 0):
                        raise ValueError(
                            "independent D2 source acceptance or projection differs"
                        )
                center = scaled(profiles[1]["center"])
                if not (
                    rounded_significant(center, 215)
                    == Decimal(evidence["strict215_rounded_value"])
                ):
                    raise ValueError(
                        "independent D2 source acceptance or projection differs"
                    )
                # Enclose both accepted empirical neighborhoods around the chosen
                # profile center. No probabilistic independence is assumed.
                estimate = max(
                    abs(center - scaled(p["center"])) + scaled(p["error_upper"])
                    for p in profiles
                )
                records.append(
                    {
                        "symbol": period["public_atom"]["readable"],
                        "value": str(center),
                        "significant_digits": 215,
                        "absolute_error": str(estimate),
                        "error_quality": "estimated",
                        "definition": period["portable_integral_definition"][
                            "positive_Euclidean_definition"
                        ],
                        "provenance": {
                            "source_kind": "independent convergent D2 integral; no master coefficient inversion",
                            "error_authority": "accepted two-profile empirical refinement; not an interval certificate",
                            "definition_metadata": period[
                                "portable_integral_definition"
                            ],
                            "definition": reference(root, definition_path),
                            "portable_proof_index": reference(root, index_path),
                            "acceptance": accepted_ref,
                            "validation": validation_ref,
                            "center_json_pointer": f"/periods/{position}/current_independent_auxiliary_evidence/qualified_bindings/1/center",
                            "error_rule": "max_i(abs(chosen_center-center_i)+error_upper_i)",
                            "accepted_significant_digits": 215,
                            "stored_digits_do_not_extend_source_cap": True,
                        },
                    }
                )
        readset.append(reference(root, definition_path))
    for record in records:
        if not (
            Decimal(record["absolute_error"])
            < abs(Decimal(record["value"])) * Decimal("1e-215")
        ):
            raise ValueError("independent D2 source acceptance or projection differs")
    return records, readset


def derive_taylor01(root):
    """Project only the two newly accepted first Taylor coefficients."""
    with localcontext() as context:
        context.prec = 2000
        return _derive_taylor01(root)


def _derive_taylor01(root):
    definition_path = (
        "4L/provenance/PR10-epsilon1-v25/"
        "independent-D2-Taylor01-period-registry-v2.json"
    )
    producer_index_path = "provenance/PR10-epsilon1-v25/portable-proof-index.json"
    index_path = (
        "provenance/independent-d2-taylor01-runtime-v2/portable-proof-index.json"
    )
    definition = json.loads(data.checked_path(root, definition_path).read_bytes())
    producer_index = json.loads(
        data.checked_path(root, producer_index_path).read_bytes()
    )
    index = json.loads(data.checked_path(root, index_path).read_bytes())
    if definition["portable_validation_proof_index"] != reference(
        root, producer_index_path
    ):
        raise ValueError("independent D2 Taylor source authentication differs")
    records = []
    for symbol, name, slot in [
        ("vakint::PR10D2Eps1", "E10", 2),
        ("vakint::PR7D2Eps1", "P7", 5),
    ]:
        periods = [p for p in definition["periods"] if p["public_symbol"] == symbol]
        if len(periods) != 1:
            raise ValueError("independent D2 Taylor identities differ")
        period = periods[0]
        key = f"{name}_delta1"
        if not (
            period["Taylor_order"] == 1
            and period["coefficient_key"] == key
            and period["accepted_source_cap"] == 215
            and period["Taylor_coefficient_not_factorial_scaled_derivative"]
            and period["independently_defined_integral_not_target_remainder"]
            and period["public_atom"]["readable"] == symbol
        ):
            raise ValueError("independent D2 Taylor source acceptance differs")
        accepted, accepted_ref = archive(
            root,
            producer_index,
            period["independent_auxiliary215_Root_adoption"]["sha256"],
        )
        validation, validation_ref = archive(
            root, index, period["full_unrounded_error_owner"]["sha256"]
        )
        if name == "E10":
            acceptance_flag = "accepted_actual_E10_E15_Taylor0through2_auxiliary215"
            validation_flag = "two_fresh_numerical_profiles_validated_at215"
            profile_refs = accepted["original_independent_profiles"]
            profile_schema = (
                "vacuum-masters.D2-delta0to2-auxiliary215-geometric8-native-profile.v1"
            )
            validation_schema = (
                "vacuum-masters.D2-jets-auxiliary215-two-profile-validation.v1"
            )
            acceptance_schema = (
                "vacuum-masters.Root-E10-E15-order2-auxiliary215-adoption.v1"
            )
            empirical_flag = "numerical_accuracy_evidence_not_interval_proof"
            profile_ids = ["jet2-A-W280", "jet2-B-W340"]
        else:
            acceptance_flag = "accepted_actual_independent_P7_Taylor0through1_auxiliary215"
            validation_flag = "two_fresh_physical_and_source_sensitivity_profiles_passed"
            profile_refs = accepted["profiles"]
            profile_schema = "vacuum-masters.PR7-firstjet215-consumer-native-profile.v1"
            validation_schema = "vacuum-masters.PR7-firstjet215-two-profile-validation.v1"
            acceptance_schema = "vacuum-masters.root-actual-independent-P7-firstjet215-adoption.v1"
            empirical_flag = "empirical_numerical_evidence_not_interval_proof"
            profile_ids = ["jet1-A-W280", "jet1-B-W340"]
        if not (
            accepted["schema"] == acceptance_schema
            and accepted[acceptance_flag] is True
            and accepted[empirical_flag] is True
            and accepted["accepted_auxiliary_significant_digits"] == 215
            and accepted["actual_validation"] == period["full_unrounded_error_owner"]
            and validation["schema"] == validation_schema
            and validation["auxiliary_digits"] == 215
            and validation["empirical_not_interval_proof"] is True
            and validation[validation_flag] is True
            and validation["native_weighted_seed_errors_and_full_vector_source_identities_checked"]
            and validation["primal_dual_matching_and_atomic_native_checkpoint_receipts_checked"]
            and len(profile_refs) == 2
        ):
            raise ValueError("independent D2 Taylor source acceptance differs")
        evidence = [e for e in validation["coefficient_evidence"] if e["key"] == key]
        if len(evidence) != 1:
            raise ValueError("independent D2 Taylor coefficient evidence differs")
        evidence = evidence[0]
        center = Decimal(evidence["raw_center"])
        profiles = []
        neighborhoods = []
        for position, profile_ref in enumerate(profile_refs):
            profile, portable_ref = archive(root, index, profile_ref["sha256"])
            model = profile["coefficient_models"][slot]
            if not (
                profile["schema"] == profile_schema
                and profile["profile_id"] == profile_ids[position]
                and profile["auxiliary_target_digits"] == 215
                and profile["unknown_period_or_D4_target_value_used"] is False
                and profile["empirical_not_interval_proof"] is True
                and profile["atomic_checkpoint_native_exact_disk_readback_passed"]
                and profile["finite_working_reconstruction_rounding_propagated"]
                and model["period"] == name
                and model["delta_order"] == 1
                and model["slot"] == slot
                and model["empirical_not_interval_proof"] is True
                and Decimal(model["center"][1]) == 0
                and Decimal(model["total_empirical_error_abs"][1]) == 0
            ):
                raise ValueError("independent D2 Taylor profile differs")
            profile_center = Decimal(model["center"][0])
            profile_error = Decimal(model["total_empirical_error_abs"][0])
            if not (
                profile_center.is_finite()
                and profile_error.is_finite()
                and profile_error > 0
            ):
                raise ValueError("independent D2 Taylor decimal differs")
            profiles.append((profile_center, profile_error))
            neighborhoods.append(
                {
                    "profile_id": profile["profile_id"],
                    "source": portable_ref,
                    "center_json_pointer": f"/coefficient_models/{slot}/center/0",
                    "error_json_pointer": f"/coefficient_models/{slot}/total_empirical_error_abs/0",
                }
            )
        estimate = max(abs(center - c) + e for c, e in profiles)
        cell = evidence["strict215_cell"]
        if not (
            center == profiles[1][0]
            and Decimal(evidence["crossprofile_difference"])
            == abs(profiles[0][0] - profiles[1][0])
            and validation["strict215_rounding_cells"][key] == cell
            and (name != "E10" or accepted["strict215_rounding_cells"][key] == cell)
            and rounded_significant(center - estimate, 215) == Decimal(cell)
            and rounded_significant(center + estimate, 215) == Decimal(cell)
            and estimate < abs(center) * Decimal("1e-215")
        ):
            raise ValueError("independent D2 Taylor finite cap differs")
        records.append(
            {
                "symbol": symbol,
                "value": str(center),
                "significant_digits": 215,
                "absolute_error": str(estimate),
                "error_quality": "estimated",
                "definition": period["mathematical_definition"]
                + "; "
                + period["portable_integral_definition"]["positive_Euclidean_definition"],
                "provenance": {
                    "source_kind": "independent convergent D2 integral Taylor coefficient; no master coefficient inversion",
                    "error_authority": "both accepted full empirical profile neighborhoods; not an interval certificate",
                    "definition_metadata": period,
                    "definition": reference(root, definition_path),
                    "producer_portable_proof_index": reference(root, producer_index_path),
                    "portable_proof_index": reference(root, index_path),
                    "acceptance": accepted_ref,
                    "validation": validation_ref,
                    "coefficient_key": key,
                    "center_json_pointer": f"/coefficient_evidence/{slot}/raw_center",
                    "profile_neighborhoods": neighborhoods,
                    "error_rule": "max_i(abs(chosen_B_center-center_i)+total_empirical_error_abs_i)",
                    "accepted_significant_digits": 215,
                    "stored_digits_do_not_extend_source_cap": True,
                },
            }
        )
    return records, [
        reference(root, path)
        for path in [definition_path, producer_index_path, index_path]
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--adapter", choices=["d2-v1", "taylor01-v2"], default="d2-v1")
    args = parser.parse_args()
    with localcontext() as context:
        context.prec = 2000
        records, readset = (
            derive(args.root) if args.adapter == "d2-v1" else derive_taylor01(args.root)
        )
    filename = "constants-d2.json" if args.adapter == "d2-v1" else "constants-d2-taylor01.json"
    schema = (
        "vakint.external-data.independent-d2-runtime-projection.v1"
        if args.adapter == "d2-v1"
        else "vakint.external-data.independent-d2-taylor01-runtime-projection.v2"
    )
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / filename).write_text(json.dumps(records, indent=2) + "\n")
    (args.output / "projection.json").write_text(
        json.dumps(
            {
                "schema": schema,
                "accepted": True,
                "no_new_numerical_calculation": True,
                "no_master_coefficient_inversion": True,
                "all_errors_estimated_not_bounded": True,
                "readset": readset,
                "output_sha256": digest(
                    (args.output / filename).read_bytes()
                ),
                "script_sha256": digest(Path(__file__).read_bytes()),
            },
            indent=2,
        )
        + "\n"
    )
    for record in records:
        print(
            record["symbol"],
            record["significant_digits"],
            record["error_quality"],
            record["value"][:36],
            str(Decimal(record["absolute_error"])).split("E")[-1],
        )


if __name__ == "__main__":
    main()
