# Vakint external data

The 31 October 2026 source update rewrites every exact 1L–4L coefficient row (739 rows
of 115 masters, 713 distinct coefficients) in one basis of 68 constants, with common
factors pulled out and terms collected; see [`docs/basis.md`](docs/basis.md). The
generators are pi, zeta(3), zeta(5), zeta(7), log 2, Li4/5/6(1/2), the alternating sum
`s6weak`, log 3, Cl2(pi/3), Cl4(pi/3), Im Li3(i/sqrt3), Im Li4(i/sqrt3), four sixth-root
GPLs, the MATAD constants D5bar1/2, D6bar1/2 and T111bar4, ten Bessel moments and jets,
30 D=2-2delta periods, and five weight-7 or D=4-2eps constants; `3^(1/2)` is an explicit
parity factor. The coefficients shrink from 20,971 to 6,645 terms. Each new row equals its
previous row once the identities listed in the publication receipt are applied. Most are
published reduction tables or proved identities. Some are numerical identities, not proofs:
the 48-term relation R1 among the D=2 jets, which removes `PR11dD2Eps2` (identical to
relation (c30) of arXiv:1609.05071 where comparable, verified to 547 digits); the two
identities that replace Im G(0,1,-omega) and Im G(0,1,1,-omega) by Im Li3(i/sqrt3) and
Im Li4(i/sqrt3) (4,100 digits); and the earlier BNbar4 and Li3(i/sqrt3) reductions and
the closed formula of `PR11dep0` (544 digits). Integer-relation searches at about 500 digits for
the hard constants and 5,000 for the classical ones find no other stable relation among
the generators or the products that occur. Possible jet-3 and jet-4 analogues of R1 are
not excluded at the available precision. Rows no longer use the coefficient aliases
`PR11dep0`, `PR4fin` and `PR4dfin`, the derived MATAD constants `S2`, `T1ep`, `T1ep2` and
`BNbar4`, the HPL words, or `PR10D2`, `PR15D2`, `PR5D2Eps3` and `PR11dD2Eps2`, whose
`4L/constants.json` records stay unchanged. Three
three-loop rows write `s6weak` through its built-in GPL definition, because the four-loop
constants are not loaded for three-loop use. `PR12D2Eps3` is now validated: its
closure-implied control of at least 421 digits was accepted. Every `numerical.json`,
numerical precision record and constant value is unchanged, as is the five-loop data. See
[`provenance/takeover-basis-v4-rewrite-v1`](provenance/takeover-basis-v4-rewrite-v1).

A second 30 October 2026 source update replaces the numerical values of 644 of the
739 lower-loop coefficient rows (112 three- and four-loop masters) by the values of
their published exact formulas. Each formula was evaluated at 20,100 and 20,200
working digits, and a row was replaced only where the formula supports more validated
digits than the stored value and the two agree within their combined errors. 585 rows
now have 20,000 validated digits (3L 250, 4L 335). 59 four-loop rows whose formulas
contain D=2 periods, `K5MomentTaylor` or MATAD constants now have 516 to 520 digits,
limited by the validated digits of those constants. The other 95 rows keep their bytes:
the 1L and 2L rows are already at 20,000 digits, 57 rows are exact zeros, and PR4/PR4d
at epsilon zero and one and PR11d at epsilon zero keep their bounded 20,000-digit values.
The new errors are first-order estimates (`error_quality` `"estimated"`), not interval
proofs. Exact formulas, constants and the five-loop data are unchanged. See
[`provenance/symbolic-expression-evaluation-v1`](provenance/symbolic-expression-evaluation-v1).

The first 30 October 2026 source update closes the four-loop window: the 43 coefficients
that were numerical fallbacks now have exact formulas, so all 444 coefficients
(epsilon^-4 through epsilon^1) of the 74 four-loop masters are symbolic. The new
formulas use known constants and named D=2-2delta periods, D=4-2eps master
coefficients and MATAD constants installed in `4L/constants.json` with 520 to 650
validated digits (`s6weak`: 20,000). Each formula reproduces the independent
500-digit numerical values of its masters. Every constant record now also carries a
`symbolic_definition`, a Symbolica atom of its defining integral. Numerical values,
their precision and the five-loop publication are unchanged. This source update
creates no new release and does not change `data-latest`.

The 28 October 2026 source update gave all six coefficients of 26 selected
four-loop masters at least 500 validated digits; the three PR11d finite aliases
retain their stronger 20,000-digit values and bounded evidence.

Versioned native RustRed reductions, master-integral Laurent coefficients and
graphs, and prepared reduction caches for
[Vakint](https://github.com/alphal00p/gammaloop/tree/6cdaa993ee9b413189ae077a8f783de6223cc42e/crates/vakint).
The data originates in Vakint's former `artifacts` directory. Original lower-loop
payloads and migration checksums are retained; previous five-loop publications
remain available through Git history.

Each release has separate `1L` through `5L` compressed packs. Loading a maximum
loop count installs all packs up to that count. `data-latest` points to the
current immutable release through its `manifest.json`; exact versions remain
available independently.

An immutable release may also declare optional source evidence in the root
manifest's `provenance_assets` list. Each row contains `archive`,
`archive_sha256`, and `archive_bytes`: a versioned filename such as
`vakint-external-data-v0.1.2-cache-build-evidence.tar.gz`, its lowercase SHA-256,
and a positive byte length strictly below 2,000,000,000. Keep these large files
outside Git. They are evidence downloads, not runtime caches or loop packs.
Every release archive, including each loop pack, must satisfy that size bound.

After finalizing the release version and committing those static metadata rows,
place exactly the declared regular files in a separate directory and run:

```sh
python3 tools/data.py pack --output /path/to/release --provenance-assets /path/to/evidence
python3 tools/publish.py /path/to/release
```

Packing verifies and copies the files and includes them in `SHA256SUMS`.
Publication verifies the same committed metadata and all asset identities before
any release mutation, publishes the immutable assets first, and updates the
alias manifest last. Older versioned assets remain available through the alias.
Without `provenance_assets`, the existing packing and publication behavior is
unchanged and the extra argument is unnecessary. Version changes require
removing the old version's evidence rows and authoring the new ones explicitly.

CI can validate the same deterministic runtime packs without downloading source
evidence by running `python3 tools/data.py pack --runtime-only --output PATH`
with an empty output directory. This preserves the release manifest and runtime
archive bytes, records omitted evidence in checksummed `RUNTIME_ONLY.json`, and
produces **nonpublishable** validation artifacts. The publisher rejects them;
build a full release in a new directory with every declared source asset.

```python
engine.load_official_external_data(4)
engine.load_official_external_data(4, version="v0.1.1", local_artifacts_path="/path/to/data")
```

A checkout of this repository can be passed directly as `local_artifacts_path`
and is validated without network access. Source manifests leave archive hashes
unset; release manifests contain them. All loop-manifest paths are relative to
their loop directory.

1L–4L contain 115 computed masters in total. The 640 declared 5L campaign
terminals have graphs and exact identities, but **no computed coefficients**.
The five-loop graph files retain the complete numerator, propagator powers,
mass terms and explicit loop-momentum basis. Their names `P1` through `P640`
are assigned anew for this publication; match integrals by their family-qualified
signed index tuples, not by names from older releases. The selected five-loop
LIGHT cache contains 2,102 strict-complete records (54 Route and 2,048 Apply)
in one 89,635,796-byte native gzip file. The user froze this existing validated
candidate as adequate; this is not a measured performance winner. It supplies
no five-loop epsilon coefficients.
See [`5L/cache/README.md`](5L/cache/README.md) for exact selection and compatibility scope.
Prepared 1L–4L caches complete a declared finite workload; this does not certify
arbitrary-index IBP coverage. See `coverage.json` and `cache.json` in each pack.

The current five-loop source is recorded in
[`5L/provenance/current-publication.json`](5L/provenance/current-publication.json),
and its admitted starting queries remain in the native application package.
The rank and power-difference maxima summarize those predicates; they do not
assert coverage of every index tuple below the maxima. Historical records under
`provenance/original-root` are immutable migration evidence and do not define the
current five-loop basis.

Load the new five-loop source checkout explicitly, without downloading an older
release:

```python
engine.load_external_data("/path/to/vakint-external-data", max_loop_count=5)
```

Five-loop evaluation is symbolic until numerical coefficients are supplied.
The selected file has actual Native `c2ca815` export/reimport validation for all
2,102 records, exact coefficients and ordered guards, with no missing or partial
records. Its authenticated usage comes from the frozen tuning and physical
inputs; no final held-out outcomes selected its records. Original measurement
and exporter cohorts remain separate. The previous two-root fallback, its
producer/consumer evidence and original manifests are preserved under
[`provenance/replaced-fallback-20261028`](provenance/replaced-fallback-20261028).
All five-loop noncache files, including their historical README, remain the
unchanged input-data authority. Current cache status is recorded in
[`5L/cache.json`](5L/cache.json) and [`5L/cache/README.md`](5L/cache/README.md).

For a subsequent five-loop refresh, use `tools/replace_five_loop.py stage` with
the exported native application and its native terminal definitions, validate
the staged pack, and then use its explicit `install` command with an external
backup directory. This preserves all 1L–4L payloads and their root-manifest
entries. The historical all-loop `tools/data.py generate` command refuses to
overwrite a current five-loop publication. Staging and installing a source
update do not publish a GitHub release or change `data-latest`.

The lower-loop data contains 739 numerical coefficient rows: 739 have exact
symbolic expressions and 0 retain numerical fallbacks. These counts include
49 additional orders preserved from the previous export.
The six-coefficient windows have 20,000 validated digits at 1L and 2L. Every
nonzero three-loop coefficient now has 20,000 validated digits; the two exact-zero
rows of D6 keep their 2,000-digit entries. At 4L, every nonzero coefficient has at
least 516 digits: 34 windows have 20,000 digits in every row, 6 more in every nonzero
row (their exact zeros keep 200 or 500-digit entries), and the other 34 contain rows
at 516 to 520 digits. These values are
evaluations of the exact formulas, with estimated errors (publication
`symbolic-expression-evaluation-v1`). PR4/PR4d at epsilon zero and one, and PR11d at
epsilon zero, retain their 20,000-digit values and bounded errors. The 28 October
500-digit evidence used independent numerical refinements through 520 digits; it
remains the validation data of the formulas and is not an interval proof.
Per-coefficient limits remain authoritative; exact formulas can support greater
precision subject to the finite periods they contain.
An [additive oracle correction](validation/bessel-20000-anchor-one/coverage-correction.json)
supplies the missing reference at the actual integration anchor 1; the original
certificates and public numerical values are preserved unchanged.
Per-coefficient manifest entries record the actual precision, including the
separately validated extra orders.
Some exact expressions require the corresponding Vakint period evaluator;
symbolic availability alone does not imply unlimited numerical precision.
The 24 newly accepted PR4-family coefficients preserve the upstream exact
`vakint::K5Moment` and `vakint::K5LogMoment` formulas. Their four primitive
bindings in `4L/constants.json` carry independently integrated, bounded
20,000-digit values; the logarithmic moments include the factor three and
the `EulerGamma-log(2)` shift. These are finite capabilities, not arbitrary
precision evaluators. The independent symbolic and numerical payloads retain
their own availability and provenance.
PR11dep0 and its three direct master aliases share one authenticated finite
payload. Two bounded production profiles and two isolated standard-library
verifier runs certify its 20,000 validated digits and 20,008 stored digits.
The [portable proof index](validation/pr11d-20000/proof-index.json) and
[validation report](validation/pr11d-20000-reports/PR11D_VALIDATION_REPORT_FINAL.md)
record the normalization, error bound, and scope of the independent evidence.
Large proof objects are source-only evidence outside the downloadable loop packs;
loading or using Vakint does not execute their verifier or require Mathematica.

The PR14 epsilon-one formulas use `vakint::GPLReal`/`vakint::GPLImag` components
supported by the updated Vakint/Symbolica evaluator. Independent 400-digit
component references and a separate 20,000-digit bounded-kernel validation
accompany their qualification.

The four PR7 epsilon-one expressions are direct analytic dimensional-shift
results, validated against their own 200-digit numerical coefficients. The
independent D2 integral `vakint::PR7D2` is documented in
`4L/provenance/PR7-v23/independent-D2-period.json`; its 215-digit RustFlow
validation uses an empirical refinement model, with an independent
Mathematica check at 50 digits. The additive runtime projection now supplies
this independently defined period as a finite 215-digit binding with an
explicitly estimated error. It preserves all existing numerical precision
upgrades and the four bounded 20,000-digit constant bindings.

Run `python3 tools/data.py validate` to verify payloads, coefficient availability,
cache completion receipts and migration hashes. Release and authorship
instructions are in [AUTHORING.typ](AUTHORING.typ).

The eleven PR10/PR9d/combination-B finite expressions are direct analytic results,
independently checked against their own 200-digit numerical coefficients.
Their positive Euclidean D2 periods `vakint::PR10D2` and `vakint::PR15D2`
are defined in `4L/provenance/PR10-PR15-v24/independent-D2-periods-v1.json`,
with independent 215-digit empirical evidence. The additive runtime projection
supplies these positive Euclidean periods as finite 215-digit bindings with
estimated errors covering both accepted profile neighborhoods. These are not
interval certificates or arbitrary-precision evaluators. Every existing
numerical coefficient, extra order and bounded constant record is preserved.
The reproducible projection and exact before-images are under
[`provenance/independent-d2-runtime-v1`](provenance/independent-d2-runtime-v1).
This source update does not itself create a release.

The four PR10 epsilon-one expressions are direct dimensional-recurrence results,
independently checked against their own 200-digit numerical coefficients.
The initial 22-entry PSLQ search was unstable. After exact known-lower
subtraction, Symbolica and Mathematica recovered the five-entry residual
relation [8,189,27,-274,-30] at 100/110 effective digits, using 140/150
digits of the original targets. A separately constructed native full Atom
is exactly identical to the accepted dimensional-recurrence expression,
binding this recurrence-assisted recognition to the existing 200-digit
checks. This does not claim blind full-coefficient discovery.
The positive Euclidean D2 Taylor coefficients `vakint::PR10D2`,
`vakint::PR10D2Eps1`, `vakint::PR7D2` and `vakint::PR7D2Eps1` are defined in
`4L/provenance/PR10-epsilon1-v25/independent-D2-Taylor01-period-registry-v2.json`,
with independent 215-digit empirical evidence. Existing leading definitions,
all numerical precision, extra orders and bounded constant payloads remain
unchanged. This producer update adds no numerical binding by itself; runtime bindings
are managed separately by the authenticated projection. It creates no release.

The additive Taylor runtime projection supplies only `vakint::PR10D2Eps1`
and `vakint::PR7D2Eps1` as finite 215-digit bindings. Their estimated absolute
errors cover both accepted full profile neighborhoods around the chosen
high-precision center; they remain empirical, not interval bounds. The portable
full source records, reproducible projection, exact-arithmetic review and
seven unchanged previous bindings are recorded under
[`provenance/independent-d2-taylor01-runtime-v2`](provenance/independent-d2-taylor01-runtime-v2).
The source cap stays at 215 digits despite longer stored decimals. No producer
record, numerical coefficient or existing bounded constant binding is changed.

The 30 October 2026 four-loop closures (publication
[`provenance/takeover-4L-closures-v1`](provenance/takeover-4L-closures-v1)) give the
last 43 four-loop coefficients exact formulas. They cover 17 distinct directions of
the PR9, PR9d, PR15, PR11, PR11d, PR12 and PR0 masters and their alias combinations
on 26 masters. Each formula is an exact composition of accepted dimension-shift and
DREAM maps with named periods. The new periods are positive-Euclidean D=2-2delta Taylor
coefficients `vakint::<X>D2Eps<k>` of the hat integrals
X_hat(delta) = exp(4 EulerGamma delta) int prod d^Dk/pi^(D/2) prod 1/(q^2+1)^a, with
D = 2-2delta. They are complemented by the DREAM banana coefficients
`vakint::K5MomentTaylor(k,j)`, the D=4-2eps coefficients `vakint::PR14ep2`/`PR14ep3`
of master P31, the MATAD weight-7 constants `vakint::T111bar5`, `BNbar5`, `D5bar3`
and the alternating Euler sum `vakint::s6weak`. Their definitions and evidence are in
`4L/provenance/takeover-4L-closures-v1/independent-D2-period-registry-v3.json`.
Every formula agrees with the independent 500-digit numerical values of all its
masters to within 0.483 units of the last stored digit, and with the raw numerical
profiles to 543.6 to 548.1 digits. Its recorded symbolic cap is the minimum of its
constants' digits and its first-order statement budget (516 to 519 digits).
The constants carry estimated, empirical two-profile errors, not interval proofs;
each error includes the rounding of the stored decimal (one unit of its last digit).
Every constant has an independent-method control, except `PR12D2Eps3`. Under the rule
that such a control only has to catch systematic errors (30-50 digits suffice),
`PR10D2Eps4` has one at 139.35 digits and `PR14ep3` at 424.0 digits. `PR12D2Eps3`
has two-profile validation at 520 digits; its only control is implied by the P70
epsilon-one closure itself (at least 421 digits, an inference), so that formula
remains conditional on its label. `PR5D2Eps3` stays a numerical period here; its
exact formula belongs to the later rewrite in an independent constant basis.
Every `symbolic_definition` writes out its defining integral and each normalisation
factor (measure, signs, exponential and Gamma factors, Taylor coefficient, unit
mass); none refers to another named constant. The numerical rows remain
the validation data and are unchanged, as are all numerical precisions. P17/P52/P74
at epsilon zero keep their bounded 20,000-digit values next to the new exact row.
P19/P73 at epsilon zero keep their `PR11dep0` formulas.

The finite-constant adapter `takeover-4l-closures-v3`
([`provenance/takeover-4l-closures-runtime-v3`](provenance/takeover-4l-closures-runtime-v3))
lifts `PR7D2`, `PR7D2Eps1`, `PR10D2`, `PR10D2Eps1` and `PR15D2` from 215 to 520
validated digits and adds 41 constants. The superseded 215-digit projections still
replay unchanged against the archived before-image. Each `constants.json` record may
carry an optional `symbolic_definition`, a Symbolica atom of the defining integral.
It uses the inert heads `vakint::Integral(f, vakint::Interval(x,a,b), ...)` (first
interval outermost), `vakint::LoopIntegral(D, f, vakint::k(1), ...)` (Euclidean,
measure d^Dk/pi^(D/2) per loop), `vakint::SeriesCoefficient(f, x, x0, n)` (the
coefficient of (x-x0)^n) and `vakint::EuclideanDot`. The prose `definition` is unchanged.
`PR10D2`, `PR10D2Eps1` and `PR15D2` keep their producer routing in the metadata; their
`symbolic_definition` uses the routing shared by the other Taylor coefficients of the same
integral, and the metadata records the exact loop-momentum substitution between the two.
