# Traditional constants (option A, data only)

This directory documents the constant names of this repository in traditional mathematical constants. It is additive
material: every current symbol, every coefficient file and Vakint itself are unchanged, and nothing reads this directory
at run time.

- `DICTIONARY.md`: each reducible constant (D5bar1, D5bar2, D6bar1, D6bar2, T111bar4, T111bar5, BNbar5, s6, ReG4, the
  basis-v4 generators, ...) as an exact expression in traditional generators, with the digits to which it was verified.
- `GENERATORS.md`: the traditional generator set (weights 1-7) and the definitions of its functions.
- `LIFTED-DEFINITIONS.md`: explicit integral definitions of the constants that do not reduce (Bessel moments in
  Broadhurst's notation and their eps-jets, the D = 2 four-loop constants PR*D2Eps*, PR14ep*, and D5bar3).
- `RELATIONS.md`, `REPORT.md`: the relations found and the method (lattice reduction, blind re-finding, full-digit checks).
- `CONSTANTS-TRADITIONAL.md`: the table used by the Vakint benchmark document.
- `rewrite-table.json`: the machine-readable OPTIONAL rewrite table (name -> rational combination of generator monomials,
  generator values, verified digits; D5bar3: undecided).

`tests/test_traditional_constants.py` re-evaluates every entry from the generator values in the table, with Python's
`decimal` module only. T111bar5, BNbar5 and s6 (stored as `vakint::s6weak`) are checked against `4L/constants.json` to
their full stored digits. The other constants are Vakint built-ins whose values this repository does not store; they are
checked against the independent reference values carried in the table, to 1000 digits. Their full 20000-digit check
(recorded as `verified_digits`) was made with the generator evaluators of the derivation, which this repository does not
contain.

A later release may rewrite the 3L and 4L coefficient files in these constants, keeping the old names as aliases.
