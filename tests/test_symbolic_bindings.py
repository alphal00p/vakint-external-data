"""Every vakint:: leaf of a published exact row must be bound.

Vakint ranks an exact formula with an unbound vakint:: leaf as arbitrary
precision, prefers it over the numerical row and then cannot evaluate it.
Exact rows may therefore only use Vakint's built-in special functions and
constants, the recorded period aliases, or symbols of the loop's constants.json.
"""

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import data

BUILTIN_FUNCTIONS = {"HI", "HR", "GPLReal", "GPLImag"}
BUILTIN_CONSTANTS = {"S2", "T1ep", "T1ep2"}
RECORDED_PERIODS = {"PR4fin", "PR4dfin", "PR11dep0", "PR4ep1", "PR4dep1"}
LEAF = re.compile(r"vakint::([A-Za-z_][A-Za-z0-9_]*)(\([0-9, ]*\))?")


def exact_rows(loops):
    manifest = data.read_json(data.ROOT / f"{loops}L/manifest.json")
    for master in manifest["masters"]:
        if "symbolic.json" not in master["files"]:
            continue
        rows = dict(
            data.read_json(
                data.ROOT / f"{loops}L" / master["files"]["symbolic.json"]["path"]
            )
        )
        for coefficient in master["coefficients"]:
            if coefficient["symbolic"]:
                yield master["name"], coefficient["epsilon_power"], rows[
                    coefficient["epsilon_power"]
                ]


class SymbolicBindingTests(unittest.TestCase):
    def test_every_exact_row_leaf_is_builtin_recorded_or_a_bound_constant(self):
        for loops in range(1, 5):
            path = data.ROOT / f"{loops}L/constants.json"
            constants = (
                {record["symbol"] for record in data.read_json(path)}
                if path.exists()
                else set()
            )
            for name, power, formula in exact_rows(loops):
                for head, arguments in LEAF.findall(formula):
                    if head in BUILTIN_FUNCTIONS:
                        continue
                    symbol = f"vakint::{head}{arguments.replace(' ', '')}"
                    with self.subTest(loops=loops, master=name, power=power, leaf=symbol):
                        self.assertTrue(
                            head in BUILTIN_CONSTANTS
                            or head in RECORDED_PERIODS
                            or symbol in constants,
                            f"unbound exact-row leaf {symbol}",
                        )

    def test_four_loop_window_is_fully_exact(self):
        manifest = data.read_json(data.ROOT / "4L/manifest.json")
        window = [
            coefficient
            for master in manifest["masters"]
            for coefficient in master["coefficients"]
            if coefficient["numerical"] and -4 <= coefficient["epsilon_power"] <= 1
        ]
        self.assertEqual(len(window), 444)
        self.assertTrue(all(coefficient["symbolic"] for coefficient in window))

    def test_exact_rows_contain_no_float_literals(self):
        for loops in range(1, 5):
            for name, power, formula in exact_rows(loops):
                with self.subTest(loops=loops, master=name, power=power):
                    self.assertIsNone(
                        re.search(r"[0-9]\.[0-9]|[0-9][eE][-+]?[0-9]", formula)
                    )


if __name__ == "__main__":
    unittest.main()
