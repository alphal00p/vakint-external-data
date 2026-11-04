# Five-loop symbolic reduction

This pack contains 131 unevaluated terminal integrals and the native
RustRed application for the recorded campaign scope. Each `masters/P*/graph.dot`
contains its complete numerator, masses, powers and explicit loop basis.
The scalar model is `model.json`. No numerical coefficients are supplied.

The exact signed-index identity is recorded in `manifest.json`; P-numbers are
display names for this publication only. See `coverage.json` for admitted scope.

## Derived files of this release (RT, 2026-11-04)

- `route-preparation.rrbin` (manifest section `route_preparation`) was regenerated for this application with vakint's `five_loop_route_preparation` example (vakint 0.2.0, RustRed 3e83ae91) and checked by reloading the application from it (identical routes). RustRed rejects a stale add-on and verifies every route instead.
- No 5L Ordered step cache is shipped (no `ordered_cache` section): the v0.2.0 cache recorded the steps of the 640-master application (program rule tables a244b9b4...); this application has different rule tables, so Vakint would reject that cache and run without it. The 1L-4L Ordered caches are unchanged.
- The depth-first prepared cache shipped by earlier releases under `cache/` is retired (`cache` is `{"available": false}`), as in vakint-external-data v0.2.0; the repository's `provenance/retired-dfs-caches-v1` records the removed files.
