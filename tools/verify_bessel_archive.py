#!/usr/bin/env python3
"""Verify the archived acceptance chain and corrected oracle coverage.

The default check needs only Python's standard library. --replay-balls requires
python-flint==0.9.0 and rechecks both partitions and the exact reconstruction.
Neither mode invokes Mathematica, downloads data, or rewrites accepted files.
The additive anchor-one receipt is checked alongside the immutable original.
"""

import argparse
import importlib.util
from pathlib import Path

import data
import precision_supplement


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=data.ROOT)
    parser.add_argument("--replay-balls", action="store_true")
    args = parser.parse_args()
    receipt = precision_supplement.load_source(args.root)
    if receipt is None:
        raise ValueError("no accepted numerical precision supplement")
    payload = data.read_json(args.root / receipt["provenance"]["payload"]["path"])
    if args.replay_balls:
        archive = (args.root / receipt["provenance"]["validation"]["path"]).parent
        spec = importlib.util.spec_from_file_location(
            "archived_bessel_validator", archive / "validate.py"
        )
        validator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(validator)
        validator.ctx.dps = validator.DIGITS + 350
        validator.ctx.threads = 1
        _, primary, _ = validator.complete_profile("a")
        _, independent, _ = validator.complete_profile("b")
        values = [
            validator.independent_reconstruct(profile)
            for profile in [primary, independent]
        ]
        for row in payload["constants"]:
            primitive = "PR4fin" if row["master_basis"] == "vakint::PR4" else "PR4dfin"
            component = "value" if row["epsilon_power"] == 0 else "epsilon1_value"
            left, right = (value[primitive][component] for value in values)
            if not left.overlaps(right):
                raise ValueError(f"independent intervals differ: {row['symbol']}")
            for value in [left, right]:
                center, error = validator.rounded_cell(
                    value, row["stored_significant_digits"]
                )
                bound = validator.arb(row["validation"]["absolute_error_bound"])
                if center != row["numerical_value"] or bound.lower() < error.upper():
                    raise ValueError(
                        f"published decimal or error bound differs: {row['symbol']}"
                    )
    print(
        f"Verified {len(payload['constants'])} accepted Bessel coefficient records"
        + (
            " and replayed both Arb enclosures"
            if args.replay_balls
            else " and their proof hashes, including corrected oracle anchor coverage"
        )
    )


if __name__ == "__main__":
    main()
