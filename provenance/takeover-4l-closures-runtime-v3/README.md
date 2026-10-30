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

Values are projections of archived, already validated producer registries
(`objects/`, indexed by `portable-proof-index.json`; the period registry is
`4L/provenance/takeover-4L-closures-v1/independent-D2-period-registry-v3.json`).
The absolute error is the exact sum of the recorded empirical error terms of the
two profiles (agreement plus per-profile error claims, or the producer's frozen
two-profile model, plus the storage rounding of the published centre), rounded up
to six significant digits. All errors are `estimated`: empirical two-profile
statements under the campaign precedent, not interval certificates. Stored digits
do not extend the validated cap. `vakint::PR10D2Eps4`, `PR12D2Eps3` and `PR14ep3`
have two-profile validation only; their independent-method control is pending (P2).

Replay from the repository root:

```sh
python3 tools/d2_constants.py . /path/to/output --adapter takeover-v3
```

`review.json` is an independent exact-rational recomputation of every value cell and
error envelope from the archived sources.
