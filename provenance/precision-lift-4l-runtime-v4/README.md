# Precision lift of 45 four-loop constants (adapter `precision-lift-4l-v4`)

This adapter supersedes 45 records of `4L/constants.json` that the adapter `takeover-4l-closures-v3` owns: the 41 non-built-in
generators of the constant basis v4 (`docs/basis.md`) and the dependent records `vakint::PR10D2`, `vakint::PR15D2`,
`vakint::PR5D2Eps3` and `vakint::PR11dD2Eps2`. Only values, digit counts, errors and value provenance change. The records keep
their prose `definition`, `symbolic_definition` and `definition_metadata`, and the other five records
(`K5Moment(1|3)`, `K5LogMoment(1|3)`, `s6weak`) stay byte-identical. The takeover projection still replays unchanged against the
archived before-image `before/4L/constants.json`.

Source: the campaign's validated precision registry (tracks PREC, 4 November 2026, and PREC2, 5 November 2026, plus the review
PREC2-REVIEW-2 on 6 November). It is archived byte for byte in `objects/` and indexed by `portable-proof-index.json`, together with
the PREC and INDEP reports. The registry stores each value with exactly its validated number of significant digits. A digit counts as
validated when it is within the certified ball digits of both profiles and within their agreement, minus 2 digits, or minus 5 when the
series truncation is heuristic. Nothing beyond those digits is stored here. Each value cell of `registry.json` follows the takeover-v3
rule. Its absolute error is the sum of three terms, rounded up to six significant digits:

- the archived error bound of the centre, rounding to the validated digits included;
- the two-profile agreement floor `|centre| 10^-floor(agreement)`, when the agreement is numeric;
- one unit of the last stored digit.

The published `significant_digits` is the largest count below the stored digits that this error supports. That is the validated
count minus 1 for 34 records and minus 2 for 11. Errors stay `estimated`.

Checks (exact arithmetic):

- `tools/d2_constants.py --adapter precision-lift-v4` reproduces `constants-precision-lift-v4.json`.
- `tools/finite_constants.py` additionally requires that every new value lies inside the superseded record's stated
  `absolute_error`, that the digits increase, and that the definitions are unchanged.
- `review.json` is a separate exact-fraction recomputation of every cell. It checks the archive hashes, that the centre equals the
  archived source, that the stored digits are the validated digits, the storage-rounding term, the rounded-up error, the digit claim,
  and agreement with the superseded record on all of its significant digits.
- `identity-checks.json` evaluates INDEP's registered predictions (registered 4 November 2026 20:17Z, before these digits existed) at the published values. R1 holds to 5361.38 digits (PASS). The
  closed formula of PR11dep0 holds to 5364.06 digits (PASS).

Labels (`provenance.validation.digits_label`, `independent`). PR12D2Eps2/3, PR15D2Eps1-3 and PR0D2Eps1/2 rest on two profiles of
one code and are not independent. An integer-relation (PSLQ) excess count has to use `prec_validated_digits_strict` and, for these
records, say that it relies on two-profile digits. For PR14ep2/3, PR5D2Eps4 and D5bar3, two independent implementations agree only
to the strict digits (5060).

The previous records agree with the new values on all of their claimed digits. The seven wheel jets
PR11D2Eps2-4 / PR11dD2Eps1-4 previously stored 600-603 digits but were accurate only to 591-596 (inside their stated errors). Their
stored tails were not significant; see `supersedes.previous_stored_decimal_check`.

| constant | previous digits | validated (stored) | published | strict | agreement with previous | label |
|---|---:|---:|---:|---:|---:|---|
| `vakint::PR7D2` | 520 | 5543 | 5542 | 5543 | 559.98 | single-implementation rigorous ball: two profiles of one eta-flow code (Arb-certified transport), not two independent methods |
| `vakint::PR10D2` | 520 | 5541 | 5539 | 5541 | 559.6 | derived from PR7D2 (single-implementation rigorous ball) and K5Moment(1) through the accepted identity D2J0_PR10 (GLS 1609.05071, 18000-digit PSLQ) |
| `vakint::PR15D2` | 520 | 5541 | 5540 | 5541 | 560.76 | derived from PR7D2 (single-implementation rigorous ball) and K5Moment(1) through the accepted identity D2J0_PR15 (GLS 1609.05071, 18000-digit PSLQ) |
| `vakint::PR10D2Eps1` | 520 | 5407 | 5406 | 5407 | 560.36 | single-implementation rigorous ball: two profiles of one eta-flow code (Arb-certified transport), not two independent methods |
| `vakint::PR7D2Eps1` | 520 | 5541 | 5540 | 5541 | 559.64 | single-implementation rigorous ball: two profiles of one eta-flow code (Arb-certified transport), not two independent methods |
| `vakint::PR10D2Eps2` | 520 | 5407 | 5406 | 5407 | 560.04 | single-implementation rigorous ball: two profiles of one eta-flow code (Arb-certified transport), not two independent methods |
| `vakint::PR15D2Eps1` | 520 | 2806 | 2805 | 2806 | 560.09 | two profiles of one code, not independent |
| `vakint::PR15D2Eps2` | 520 | 2603 | 2601 | 2603 | 559.97 | two profiles of one code, not independent |
| `vakint::PR7D2Eps2` | 520 | 5539 | 5538 | 5539 | 560.92 | single-implementation rigorous ball: two profiles of one eta-flow code (Arb-certified transport), not two independent methods |
| `vakint::K5MomentTaylor(1,2)` | 520 | 19702 | 19701 | 19702 | 559.98 | rigorous Arb ball, two profiles of one code |
| `vakint::K5MomentTaylor(3,2)` | 520 | 19691 | 19690 | 19691 | 561.08 | rigorous Arb ball, two profiles of one code |
| `vakint::K5MomentTaylor(1,3)` | 520 | 19702 | 19701 | 19702 | 560.23 | rigorous Arb ball, two profiles of one code |
| `vakint::K5MomentTaylor(1,4)` | 520 | 19702 | 19701 | 19702 | 560.0 | rigorous Arb ball, two profiles of one code |
| `vakint::K5MomentTaylor(3,3)` | 520 | 19691 | 19690 | 19691 | 560.19 | rigorous Arb ball, two profiles of one code |
| `vakint::K5MomentTaylor(3,4)` | 520 | 19691 | 19690 | 19691 | 560.66 | rigorous Arb ball, two profiles of one code |
| `vakint::PR5D2Eps4` | 520 | 9924 | 9923 | 5060 | 559.92 | validated digits from two profiles of one code |
| `vakint::PR5D2Eps3` | 520 | 9925 | 9924 | 9925 | 560.32 | two profiles of one code (own Arb radial) agreeing with main's exact level-2 J8 formula (a numerical identity, ACCEPTED-260) to 10010 d |
| `vakint::PR9D2Eps1` | 520 | 5533 | 5531 | 5533 | 544.49 | single-implementation rigorous ball: two profiles of one eta-flow code (Arb-certified transport), not two independent methods |
| `vakint::PR9D2Eps2` | 520 | 5530 | 5529 | 5530 | 544.86 | single-implementation rigorous ball: two profiles of one eta-flow code (Arb-certified transport), not two independent methods |
| `vakint::PR9D2Eps3` | 520 | 5528 | 5527 | 5528 | 545.91 | single-implementation rigorous ball: two profiles of one eta-flow code (Arb-certified transport), not two independent methods |
| `vakint::PR9pD2Eps2` | 520 | 5529 | 5527 | 5529 | 544.63 | single-implementation rigorous ball: two profiles of one eta-flow code (Arb-certified transport), not two independent methods |
| `vakint::PR9pD2Eps3` | 520 | 5527 | 5525 | 5527 | 544.38 | single-implementation rigorous ball: two profiles of one eta-flow code (Arb-certified transport), not two independent methods |
| `vakint::PR10D2Eps3` | 520 | 5405 | 5404 | 5405 | 545.23 | single-implementation rigorous ball: two profiles of one eta-flow code (Arb-certified transport), not two independent methods |
| `vakint::PR15D2Eps3` | 520 | 2353 | 2351 | 2353 | 544.4 | two profiles of one code, not independent |
| `vakint::PR7D2Eps3` | 520 | 5539 | 5538 | 5539 | 544.53 | single-implementation rigorous ball: two profiles of one eta-flow code (Arb-certified transport), not two independent methods |
| `vakint::PR9D2Eps4` | 600 | 5526 | 5525 | 5526 | 602.29 | single-implementation rigorous ball: two profiles of one eta-flow code (Arb-certified transport), not two independent methods |
| `vakint::PR9pD2Eps4` | 600 | 5525 | 5524 | 5525 | 601.56 | single-implementation rigorous ball: two profiles of one eta-flow code (Arb-certified transport), not two independent methods |
| `vakint::PR7D2Eps4` | 600 | 5536 | 5535 | 5536 | 601.73 | single-implementation rigorous ball: two profiles of one eta-flow code (Arb-certified transport), not two independent methods |
| `vakint::PR10D2Eps4` | 560 | 5404 | 5402 | 5404 | 601.4 | single-implementation rigorous ball: two profiles of one eta-flow code (Arb-certified transport), not two independent methods |
| `vakint::PR11D2Eps4` | 560 | 5360 | 5359 | 5360 | 591.32 | single-implementation rigorous ball: two profiles of one eta-flow code (Arb-certified transport), not two independent methods |
| `vakint::PR11dD2Eps4` | 560 | 5358 | 5357 | 5358 | 590.64 | single-implementation rigorous ball: two profiles of one eta-flow code (Arb-certified transport), not two independent methods |
| `vakint::PR11D2Eps2` | 587 | 5363 | 5361 | 5363 | 595.81 | single-implementation rigorous ball: two profiles of one eta-flow code (Arb-certified transport), not two independent methods |
| `vakint::PR11D2Eps3` | 586 | 5361 | 5359 | 5361 | 592.52 | single-implementation rigorous ball: two profiles of one eta-flow code (Arb-certified transport), not two independent methods |
| `vakint::PR11dD2Eps1` | 588 | 5364 | 5363 | 5364 | 595.02 | single-implementation rigorous ball: two profiles of one eta-flow code (Arb-certified transport), not two independent methods |
| `vakint::PR11dD2Eps2` | 586 | 5361 | 5360 | 5361 | 593.66 | single-implementation rigorous ball: two profiles of one eta-flow code (Arb-certified transport), not two independent methods |
| `vakint::PR11dD2Eps3` | 585 | 5360 | 5358 | 5360 | 591.73 | single-implementation rigorous ball: two profiles of one eta-flow code (Arb-certified transport), not two independent methods |
| `vakint::PR12D2Eps2` | 520 | 2601 | 2600 | 2601 | 560.56 | two profiles of one code, not independent |
| `vakint::PR12D2Eps3` | 520 | 2350 | 2348 | 2350 | 559.9 | two profiles of one code, not independent |
| `vakint::PR0D2Eps1` | 520 | 2396 | 2395 | 2396 | 586.01 | two profiles of one code, not independent |
| `vakint::PR0D2Eps2` | 520 | 2397 | 2396 | 2397 | 586.17 | two profiles of one code, not independent |
| `vakint::PR14ep2` | 600 | 9926 | 9925 | 5060 | 620.28 | validated digits from two profiles of one code |
| `vakint::PR14ep3` | 600 | 9925 | 9924 | 5060 | 619.97 | validated digits from two profiles of one code |
| `vakint::T111bar5` | 650 | 19998 | 19997 | 19998 | 699.81 | rigorous Arb ball, two profiles of one code |
| `vakint::BNbar5` | 581 | 19706 | 19705 | 19706 | 699.73 | rigorous Arb ball, two profiles of one code |
| `vakint::D5bar3` | 600 | 9925 | 9924 | 5060 | 680.46 | exact tail-elimination identity applied to FIVE[4] from two profiles of one code (own Arb radial) |

Replay from the repository root:

```sh
python3 tools/d2_constants.py . /path/to/output --adapter precision-lift-v4
```

Decision: coordinator, 6 November 2026, on the user's order of 4 November 2026 to push the available digits of these periods in
vakint beyond 200 digits.
