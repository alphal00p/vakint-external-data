# Direct finite K5 primitive bindings

The four upstream symbols have exactly the independently integrated definitions:

| Symbol | Certified source moment |
|---|---|
| `vakint::K5Moment(1)` | B1 = integral of t K0(t)^5 on (0,infinity) |
| `vakint::K5Moment(3)` | B3 = integral of t^3 K0(t)^5 on (0,infinity) |
| `vakint::K5LogMoment(1)` | J1 = 3 times integral of t K0(t)^5 [log(t)+EulerGamma-log(2)] |
| `vakint::K5LogMoment(3)` | J3 = 3 times integral of t^3 K0(t)^5 [log(t)+EulerGamma-log(2)] |

`constants.json` contains independently integrated primitive values, with
20,000 validated significant digits, 20,008 uniquely rounded stored digits and
outward absolute errors. The source is the accepted 20,200-digit Bessel proof;
this export changes only the stored format and declared finite cap. No master
formula is inverted to obtain a primitive. None of these finite data records
asserts that an arbitrary-precision runtime evaluator is available.

Every source input is snapshotted and checksummed. Both independent raw moment
partitions must overlap and uniquely round to the same stored value. The
upstream definition is authenticated, including the factor three and the
EulerGamma/log(2) shift. Exact master-formula parity is reviewed separately.

With Python 3 and `python-flint==0.9.0`, reproduce the adaptation with:

```bash
python portable_replay.py --output ../fresh-K5-binding-validation
```

This replay needs neither Mathematica nor the original producer repositories.
It uses the already certified interval inputs; the larger portable Bessel proof
bundle independently replays all integration and remainder certificates.
