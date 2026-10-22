# Vakint external data

Versioned native RustRed reductions, master-integral Laurent coefficients and
graphs, and prepared reduction caches for
[Vakint](https://github.com/alphal00p/gammaloop/tree/vakint_rustred/crates/vakint).
The data originates in Vakint's former `artifacts` directory; original payloads
and their migration checksums are retained.

Each release has separate `1L` through `5L` compressed packs. Loading a maximum
loop count installs all packs up to that count. `data-latest` points to the
current immutable release through its `manifest.json`; exact versions remain
available independently.

```python
engine.load_official_external_data(4)
engine.load_official_external_data(4, version="v0.1.1", local_artifacts_path="/path/to/data")
```

A checkout of this repository can be passed directly as `local_artifacts_path`
and is validated without network access. Source manifests leave archive hashes
unset; release manifests contain them. All loop-manifest paths are relative to
their loop directory.

1L–4L contain 115 computed masters in total. The 905 declared 5L campaign
terminals have graphs and exact identities, but **no computed coefficients**.
Their nominal epsilon ranges are provenance, not available numerical data.
Prepared 1L–4L caches complete a declared finite workload; this does not certify
arbitrary-index IBP coverage. See `coverage.json` and `cache.json` in each pack.

The `v0.1.1` dataset contains 739 numerical coefficient rows:
681 have exact symbolic expressions and 58 retain numerical fallbacks. These
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
Mathematica check at 50 digits. This update adds no runtime binding or
evaluator for that symbol and preserves all existing numerical precision
upgrades and the four bounded 20,000-digit constant bindings. No new
release or change to `data-latest` accompanies this source update.

Run `python3 tools/data.py validate` to verify payloads, coefficient availability,
cache completion receipts and migration hashes. Release and authorship
instructions are in [AUTHORING.typ](AUTHORING.typ).
