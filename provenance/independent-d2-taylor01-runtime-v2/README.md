# Finite first Taylor coefficients

This adapter adds only `vakint::PR10D2Eps1` and `vakint::PR7D2Eps1` to
`4L/constants.json`. Both are independently defined positive-Euclidean D2
Taylor coefficients, with a finite source cap of 215 significant digits and
`error_quality: estimated`. No numerical integration is performed here.

The producer registry and its existing portable proof index authenticate the
Root adoptions. The additive `portable-proof-index.json` archives the exact
full error owners and both raw profiles named by those adoptions. Compressed
and uncompressed sizes and SHA256 hashes are checked before reading a source.
Historical absolute paths identify the originals; replay uses only portable
paths in this repository.

The chosen center is the full B-profile center from each coefficient's own
validation. Its runtime absolute error is exactly
`max_i(abs(center_B - center_i) + full_profile_error_i)` over profiles A and B.
This covers both complete accepted empirical neighborhoods and is larger than
the source's chosen-B summary error. It is an empirical estimate, not an
interval certificate. Longer stored decimals and higher internal working
precision do not increase the accepted source cap.

Reproduce the two-record projection from the repository root, writing to a
separate output directory:

```sh
python3 tools/d2_constants.py . /path/to/output --adapter taylor01-v2
```

`review.json` records an independent exact-rational check of both full
neighborhoods and their strict 215-digit rounding cells. The `before` files
preserve all seven previous runtime records and their binding receipt.
Validation checks those records exactly, then replays the unchanged v1
three-period projection against its original scope. The four bounded
20,000-digit bindings and all producer/scientific payloads remain unchanged.
