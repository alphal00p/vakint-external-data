# PR4 / PR4d 20,000-digit producer and proof bundle

`constants20000.json` contains PR4fin, PR4dfin and their first positive-epsilon
coefficients, each capped at 20,000 validated significant digits and storing
20,008 digits. `validation.json` is the accepted certificate. Both independent
partitions round to the same stored decimal cells; each record includes an
outward absolute error bound including storage rounding.

The optional development dependency is `python-flint==0.9.0`. This bundle is not
required by Vakint at runtime. No personal license, Symbolica license,
Mathematica license configuration, executable, or virtual environment is included.

To verify the complete accepted calculation offline after installing that Python
dependency, use a fresh sibling output directory:

```bash
python portable_validate.py --output ../bessel-validation-replay
```

The replay verifies checksums before copying inputs, recomputes all 98 independent
Mathematica-versus-Arb input checks without launching Mathematica, checks both
exact rational partitions and every analytic truncation/infinite tail, rebuilds
the D-shift independently using exact rational formal series, and verifies unique
20,008-digit rounding. It reproduces the accepted payload and receipt byte for
byte, without modifying this input bundle.

`METHOD.md` gives the mathematical derivation. Source receipts preserve the
accepted exact dimensional map and the independent earlier 200-digit Mathematica
quadrature. Historical absolute paths remain in provenance; the portable wrapper
redirects them to byte-identical bundled files, without editing accepted sources.

To regenerate the two moment profiles independently from zero, run the original
producer sequentially (approximately one CPU hour per profile; memory below
12 GiB on the validation machine):

```bash
python moments_taylor.py --digits 20000 --guard 180 --start 1 --ratio 0.2 --output fresh-primary.json
python moments_taylor.py --digits 20000 --guard 260 --start 0.75 --ratio 0.25 --output fresh-validation.json
```

The second fresh command uses the same independent starting point but a uniformly
shifted partition; it is another valid verification profile, not a byte-for-byte
reproduction of the saved mixed-step validation partition. The saved calculation
uses `h=1/4` only for its first validation interval and `h=1/5` thereafter, as
recorded in `source-manifest.json`, `parallel_moments.py`, and the individual
certificates. The original parallel runner is preserved as source provenance;
it is not an acceptance gate and must not reuse unrelated certificates.

`reconstruct.py` is the original producer-side dimensional-map conversion.
`validate.py` independently redoes that conversion using exact rational series.
The `.wl` oracle sources are optional development scripts. Their machine-specific
output locations must be adjusted for a fresh oracle run, and they require a
separately configured licensed Mathematica installation. The provided one-thread
wrapper sets internal limits. No license configuration is bundled.
