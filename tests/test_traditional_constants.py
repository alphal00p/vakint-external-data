import json
import unittest
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "provenance/traditional-constants-v1/rewrite-table.json"
REFERENCE_CHECK_DIGITS = 1000


def evaluate(entry, generators, precision):
    with localcontext() as ctx:
        ctx.prec = precision
        total = Decimal(0)
        for coefficient, monomial in entry["terms"]:
            q = Fraction(coefficient)
            value = Decimal(q.numerator) / Decimal(q.denominator)
            for name in monomial:
                value *= Decimal(generators[name]["value"])
            total += value
        if entry["normalization"] == "T/sqrt(3)":
            total *= Decimal(3).sqrt()
        return +total


def agreement(a, b):
    if a == b:
        return 10 ** 9
    with localcontext() as ctx:
        ctx.prec = 50
        return float(-(abs(a - b) / abs(b)).log10())


class TraditionalConstantsTests(unittest.TestCase):
    """Option A: the optional rewrite table re-evaluated from its generator values (decimal only)."""

    @classmethod
    def setUpClass(cls):
        cls.table = json.loads(TABLE.read_text())
        cls.stored = {c["symbol"]: c for c in json.loads((ROOT / "4L/constants.json").read_text())}

    def test_table_is_additive(self):
        self.assertEqual(self.table["option"], "A")
        self.assertEqual(self.table["entries"]["D5bar3"]["status"], "undecided")
        for entry in self.table["entries"].values():
            if "terms" in entry:
                for _, monomial in entry["terms"]:
                    for name in monomial:
                        self.assertIn(name, self.table["generators"])

    def test_stored_constants_to_their_full_digits(self):
        checked = []
        for name, entry in self.table["entries"].items():
            if "stored_value" not in entry:
                continue
            record = self.stored[entry["stored_value"]["symbol"]]
            digits = int(record["significant_digits"])
            used = min(self.table["generators"][g]["digits"] for _, m in entry["terms"] for g in m)
            self.assertGreaterEqual(used, digits + 10, name)
            value = evaluate(entry, self.table["generators"], digits + 40)
            self.assertGreaterEqual(agreement(value, Decimal(record["value"])), digits - 1, name)
            checked.append(name)
        self.assertEqual(sorted(checked), ["BNbar5", "T111bar5", "s6"])

    def test_builtin_constants_against_the_reference_values(self):
        n = 0
        for name, entry in self.table["entries"].items():
            if "reference_value" not in entry:
                continue
            value = evaluate(entry, self.table["generators"], REFERENCE_CHECK_DIGITS + 40)
            self.assertGreaterEqual(agreement(value, Decimal(entry["reference_value"]["value"])), REFERENCE_CHECK_DIGITS, name)
            n += 1
        self.assertGreaterEqual(n, 20)


if __name__ == "__main__":
    unittest.main()
