# Certified 20,200-digit PR4 / PR4d coefficients

This optional development bundle contains the complete certified Bessel-moment
inputs, all finite-interval and endpoint certificates, exact dimensional-shift
map and independent Mathematica reference values. It contains no license files,
binary kernels, personal inputs or end-user runtime dependency on Mathematica.

Install Python 3 with `python-flint==0.9.0`, then replay in a new output directory:

```bash
python portable_validate.py --output ../fresh-high-guard-validation
```

The replay uses FLINT/Arb alone. It independently checks both exact gap-free
partitions, every Frobenius/Cauchy/infinity remainder, the authenticated exact
rational dimensional-shift reconstruction, unique 20,208-significant-digit
rounding cells, outward stored-decimal error bounds and 100 independent-library
reference comparisons. It requires 20,200 validated significant digits and
reproduces the accepted payload and receipts byte for byte. A mathematically
bounded ball, rather than the independent agreement alone, certifies each digit.

`constants20200.json` supplies PR4fin, PR4dfin and their epsilon-one coefficients
in the recorded FMFT/MATAD convention. Original accepted 20,000-digit data are
preserved separately. The fresh run used four one-thread workers, roughly 26
minutes of wall time and less than 32 GiB peak aggregate memory.

The frozen first reference point list contained a spare 15/16 point instead of
the first shifted interval's true center 1. The separate fresh
`mathematica-anchor-one.json` closes this gap. Acceptance derives all 46 required
centers from exact production geometry, checks every one and retains the spare
point. The companion original-20k addendum records this correction transparently;
the original rigorous integration and rounded numbers were unaffected.

`moments_taylor.py` and `produce.py` are the optional producer. The recorded
Mathematica source scripts are independent development oracles; replay does not
execute them. Native producer and scientific provenance receipts are included
without modifying their original repositories.
