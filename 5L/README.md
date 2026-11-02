# Five-loop symbolic reduction

This pack contains 640 unevaluated terminal integrals and the native RustRed
application for the recorded campaign scope. Each `masters/P*/graph.dot`
contains its complete numerator, masses, powers and explicit loop basis.
The scalar model is `model.json`. No numerical coefficients are supplied.

The native application is the RustRed saved application under `ibps/`
(`ibps/application.json` and its compressed object parts). Two derived files
make loading and reducing it faster; neither changes a result:

- `route-preparation.rrbin` (manifest section `route_preparation`, format
  `rustred.saved-application.route-preparation.v1`) is the saved route
  verification of this application. RustRed restores it instead of re-verifying
  every transport route at load; on any mismatch it rejects the file loudly and
  recomputes.
- `ordered-cache/` (manifest section `ordered_cache`, described by
  `ordered-cache.json`) holds a trimmed RustRed Ordered step cache of the program
  `5L-tide-five-loop-common-basis`: 1,082,534 checked step records in 31 shards
  (94,257,265 bytes, no tail table) for the zero-momentum and quadratic
  benchmarks under `benchmarks/`, chosen by measured warm time saved per byte
  within the 95,000,000-byte release budget. Vakint uses it only if its stamp and
  rule tables match the running build and every file matches `manifest.json`;
  otherwise it runs the program without it. The complete cache (2,142,618
  records, 213.7 MB of shards and a 251.4 MB tail table) is kept outside this
  repository and distributed separately; see `trim` in `ordered-cache.json`.

The depth-first prepared cache shipped by earlier releases under `cache/` is
retired (`cache` is `{"available": false}`); the repository's
`provenance/retired-dfs-caches-v1` records the removed files.

The exact signed-index identity is recorded in `manifest.json`; P-numbers are
display names only. `coverage.json` describes recorded entry predicates. Cached
steps do not enlarge those predicates or prove global campaign closure.
