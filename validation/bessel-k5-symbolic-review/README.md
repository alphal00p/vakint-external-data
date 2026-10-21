# Independent PR4-family moment-binding review

This bundle checks all 24 newly published finite and epsilon-one formulas across
12 PR4-family masters. The arithmetic is exact sparse rational polynomial and
formal epsilon-series arithmetic. It also evaluates the four representative
PR4/PR4d coefficients with both sealed moment profiles and checks the finite K5
export's stored rounding and outward error bounds. No moment is reconstructed by
inverting a master value, and no alias lookup, numerical fitting, quadrature, CAS,
Git access, network access, or Mathematica is used during replay.

`original/` preserves the initial reviewer code and receipts byte for byte.
`reviewer/audit.py` differs only by redirecting input paths and Git blob reads to
the bundled immutable copies. The upstream commit is
`277e8768b37bb97141c45444f5fb94fa18177dc7`. The publication, source plan, independent
period definitions, exact dimension-shift map, accepted numerical receipt, and
profile files retain their original source hashes. The publication-to-plan-to-
definition chain is checked during replay.

Using Python with `python-flint==0.9.0`, run:

```sh
python replay.py --output /absolute/path/to/a/new/review-replay
```

The destination must not exist and must lie outside this sealed bundle. Replay
compares the complete scientific formula verdict with the original receipt,
including its 24 exact checks and 8 numerical checks. Absolute input paths and
reviewer script hashes appropriately differ in the portable receipt. The finite
payload additionally passes 8 source-ball containment and rounding checks.

The accepted runtime capability is finite 20,000 significant digits for each
stored K5 primitive. Algebraic formulas alone do not turn this payload into an
arbitrary-precision numerical evaluator. The pre-existing Bessel integration
certificate is consumed; this small replay does not repeat expensive integration.
