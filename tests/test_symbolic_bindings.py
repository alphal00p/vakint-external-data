"""Every vakint:: leaf of a published exact row must be bound.

Vakint ranks an exact formula with an unbound vakint:: leaf as arbitrary
precision, prefers it over the numerical row and then cannot evaluate it.
Exact rows may therefore only use Vakint's built-in special functions and
constants, the recorded period aliases, or symbols of the loop's constants.json.
Built-in functions with non-integer arguments (for example
vakint::PolylogImag(3,3^(1/2)*𝑖/3)) are matched by their head.
Outside the vakint namespace only the native Symbolica functions and constants
that Vakint evaluates are allowed (an unknown head would also stay unevaluated).
"""

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import data

BUILTIN_FUNCTIONS = {"HI", "HR", "GPLReal", "GPLImag", "PolylogReal", "PolylogImag"}
# Vakint built-in constants (never constants.json records): the MATAD/FMFT
# constants and the Clausen values Cl2(pi/3), Cl4(pi/3) of the constant basis.
BUILTIN_CONSTANTS = {
    "S2",
    "T1ep",
    "T1ep2",
    "cl2",
    "cl4",
    "D5bar1",
    "D5bar2",
    "D6bar1",
    "D6bar2",
    "T111bar4",
}
RECORDED_PERIODS = {"PR4fin", "PR4dfin", "PR11dep0", "PR4ep1", "PR4dep1"}
LEAF = re.compile(r"vakint::([A-Za-z_][A-Za-z0-9_]*)(\([0-9, ]*\))?")
# Non-vakint heads and symbols of published exact rows: native Symbolica
# special functions (namespaced), bare elementary functions and the builtin
# constants. Anything else is an unknown head.
NATIVE_FUNCTIONS = {"symbolica::zeta", "symbolica::polylog"}
BARE_FUNCTIONS = {"log", "exp"}
BARE_CONSTANTS = {"𝜋", "𝑖", "𝑒"}
NAMESPACED = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)::([^\W\d]\w*)")
BARE = re.compile(r"(?<![\w:])([^\W\d]\w*)(?![\w:])")


def unknown_native_heads(formula):
    """Namespaced non-vakint heads and bare identifiers outside the whitelist."""
    unknown = set()
    for namespace, name in NAMESPACED.findall(formula):
        if namespace != "vakint" and f"{namespace}::{name}" not in NATIVE_FUNCTIONS:
            unknown.add(f"{namespace}::{name}")
    for match in BARE.finditer(formula):
        name = match.group(1)
        if formula[match.end() :].startswith("("):
            if name not in BARE_FUNCTIONS:
                unknown.add(name)
        elif name not in BARE_CONSTANTS:
            unknown.add(name)
    return unknown


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

    def test_every_exact_row_uses_only_whitelisted_native_heads(self):
        seen = set()
        for loops in range(1, 5):
            for name, power, formula in exact_rows(loops):
                with self.subTest(loops=loops, master=name, power=power):
                    self.assertEqual(unknown_native_heads(formula), set())
                seen.update(
                    f"{namespace}::{head}"
                    for namespace, head in NAMESPACED.findall(formula)
                    if namespace != "vakint"
                )
        self.assertEqual(seen, NATIVE_FUNCTIONS)
        good = "symbolica::zeta(3)*log(2)+𝜋^2*vakint::S2+symbolica::polylog(4,1/2)*𝑖"
        self.assertEqual(unknown_native_heads(good), set())
        for bad, expected in [
            ("symbolica::bessel_k(0,1)", {"symbolica::bessel_k"}),
            ("symbolica::zeta(3)+python::f(2)", {"python::f"}),
            ("sqrt(3)*symbolica::zeta(3)", {"sqrt"}),
            ("Zeta(3)+log(2)", {"Zeta"}),
            ("EulerGamma*log(2)", {"EulerGamma"}),
            ("vakint::HR(1,0,om1)", {"om1"}),
        ]:
            with self.subTest(bad=bad):
                self.assertEqual(unknown_native_heads(bad), expected)

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
