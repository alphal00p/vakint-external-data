| Loop | Master keys | Six-coefficient windows ≥200 digits | ≥500 digits | ≥2,000 digits | ≥20,000 digits | Symbolic coefficients in these windows |
|---|---:|---:|---:|---:|---:|---:|
| 1L | 1 | 1 | 1 | 1 | 1 | 6/6 |
| 2L | 2 | 2 | 2 | 2 | 2 | 12/12 |
| 3L | 38 | 38 | 38 | 38 | 37 | 228/228 |
| 4L | 74 | 74 | 68 | 34 | 34 | 444/444 |
| 5L | 640 | 0 | 0 | 0 | 0 | 0/3840 |

Window counts use the smallest significant-digit entry of the six coefficients.
Exact-zero rows keep their previous entries (200, 500 or 2,000 digits); without them,
3L has 38 windows and 4L 40 windows at 20,000 digits, and every nonzero four-loop
coefficient has at least 516 digits. Values above the earlier stages are evaluations of
the exact formulas with estimated errors (`provenance/symbolic-expression-evaluation-v1`).
