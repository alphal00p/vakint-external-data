# Vakint external data

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

The `v0.1.1` dataset contains 739 numerical coefficient rows:
696 have exact symbolic expressions and 43 retain numerical fallbacks. These
counts include 49 additional orders preserved from the previous export.
The numerical fallback rows have 20,000 validated digits at 1L and 2L. Most
3L and 4L fallbacks provide 200 digits; exceptions include the three-loop D6
master at 2,000, PR4/PR4d at epsilon zero and one at 20,000, and PR11d at
epsilon zero at 20,000. The upgraded four-loop rows include bounded absolute
errors and preserved independent validation. Other orders retain their own
limits. Exact formulas can support greater precision than their archived
numerical fallbacks, subject to any finite periods they contain.
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
