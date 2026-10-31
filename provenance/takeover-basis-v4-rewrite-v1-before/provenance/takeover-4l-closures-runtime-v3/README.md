# Takeover 4L closure constants (adapter `takeover-4l-closures-v3`)

This adapter owns 46 finite constants of `4L/constants.json`:

- it lifts `vakint::PR7D2`, `PR7D2Eps1`, `PR10D2`, `PR10D2Eps1` and `PR15D2` from 215 to
  520 validated significant digits (a supersession of `independent-d2-v1` and
  `independent-d2-taylor01-v2`; their 215-digit projections still replay unchanged
  against the before-image `before/4L/constants.json`);
- it adds the 34 named periods proposed by the takeover ledger (D=2-2delta positive-Euclidean
  hat jets of PR9, dotted PR9, PR7, PR10, PR15, PR11, PR11d, PR12, PR0 and PR5, the
  DREAM banana Taylor coefficients `K5MomentTaylor(1|3,3|4)`, the D=4-2eps coefficients
  `PR14ep2`, `PR14ep3` and the MATAD weight-7 constants `T111bar5`, `BNbar5`, `D5bar3`);
- it adds `PR15D2Eps1`, `PR10D2Eps2`, `PR15D2Eps2`, `K5MomentTaylor(1,2)`,
  `K5MomentTaylor(3,2)`, `PR5D2Eps3` and the exact constant `s6weak`.

Every record (also the four retained K5 records) carries `symbolic_definition`: a
Symbolica atom of the defining (multiple) integral with the inert heads
`vakint::Integral`, `vakint::Interval`, `vakint::LoopIntegral`, `vakint::SeriesCoefficient`
and `vakint::EuclideanDot`. The prose `definition` of the retained and lifted records is unchanged.
The lifted `PR10D2`, `PR10D2Eps1` and `PR15D2` keep the producer's pinned routing in
`definition_metadata`; their `symbolic_definition` uses the routing shared by all Taylor jets of
the same object, and `definition_metadata.symbolic_definition_routing_isomorphism` records the
exact unimodular loop-momentum substitution that maps one routing onto the other.

Values are projections of archived, already validated producer registries
(`objects/`, indexed by `portable-proof-index.json`; the period registry is
`4L/provenance/takeover-4L-closures-v1/independent-D2-period-registry-v3.json`).
The absolute error is the exact sum of the recorded empirical error terms of the
two profiles (agreement plus per-profile error claims, or the producer's frozen
two-profile model) plus the storage rounding of the published centre (one unit of
its last stored digit, a `last_digit_unit` term present in every cell), rounded up
to six significant digits. `tools/d2_constants.py` rejects a cell without exactly one
storage-rounding term or with an error below one unit of the last stored digit. All
errors are `estimated`: empirical two-profile statements under the campaign precedent,
not interval certificates. Stored digits do not extend the validated cap.

Independent-method controls follow the user rule of 30 October 2026: such a control
only has to catch systematic errors (definition, normalisation, boundary data), so
30-50 digits suffice. The controls on record of the three constants that had
two-profile validation only are archived in `objects/`:

- `vakint::PR10D2Eps4`: independent-method control at 139.35 digits (radial carrier F
  and C5-95 delta^4 lifts versus the X8 eta-flow, smoke W140);
- `vakint::PR14ep3`: independent-method control at 424.0 digits (refit of the codex-2
  stage-200 D4 auxiliary-mass eta-flow samples);
- `vakint::PR12D2Eps3`: two-profile validation at 520 digits; its only control is
  closure-implied, at least 421 digits (INFERENCE, control only; ledger v2 decision D13 open).

`vakint::PR5D2Eps3` stays the numeric 520-digit period in this publication; its exact
J8 formula is a question of the later basis rewrite.

Replay from the repository root:

```sh
python3 tools/d2_constants.py . /path/to/output --adapter takeover-v3
```

`review.json` is an independent exact-rational recomputation of every value cell and
error envelope from the archived sources, including the storage-rounding checks.
