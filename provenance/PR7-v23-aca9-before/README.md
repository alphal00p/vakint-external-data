# Vakint external data

Versioned native RustRed reductions, master-integral Laurent coefficients and
graphs, and prepared reduction caches for [Vakint](https://github.com/alphal00p/vakint).
The data originates in Vakint's former `artifacts` directory; original payloads
and their migration checksums are retained.

Each release has separate `1L` through `5L` compressed packs. Loading a maximum
loop count installs all packs up to that count. `data-latest` points to the
current immutable release through its `manifest.json`; exact versions remain
available independently.

```python
engine.load_official_external_data(4)
engine.load_official_external_data(4, version="v0.1.0", local_artifacts_path="/path/to/data")
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

The unreleased `v0.1.1` source update contains 739 numerical coefficient rows:
677 have exact symbolic expressions and 62 retain numerical fallbacks. These
counts include 49 additional orders preserved from the previous export.
The 1L and 2L masters have 20,000 validated digits. The 3L and 4L numerical
coefficients provide 200 digits except the three-loop D6 master at 2,000 and
the finite and epsilon-one coefficients of PR4/PR4d at 20,000. The latter
include explicit bounded absolute errors and preserved independent validation.
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
The two newly accepted PR14 epsilon-one formulas include nine generic
`vakint::GPLReal`/`vakint::GPLImag` components outside the currently qualified
native alphabet. Their own 200-digit checks used independent 400-digit
whole-component bindings; this does not add production runtime support.
No new release or change to `data-latest` accompanies this source update.

Run `python3 tools/data.py validate` to verify payloads, coefficient availability,
cache completion receipts and migration hashes. Release and authorship
instructions are in [AUTHORING.typ](AUTHORING.typ).
