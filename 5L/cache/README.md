# Selected five-loop prepared cache

`prepared.rrcache.gz` is one native saved-application cache file with 25,088
records: two strict-complete training roots and 25,086 completed intermediates.
It is 2,456,235 bytes compressed and 16,593,448 bytes decoded, within the 50 MiB
target without an exception. Its SHA-256 is
`cc5e6d80aacc737b81be1675a8aa02694b9ccaa1e4f31cc2d5a34199e4f1a19d`.

The original producer is Vakint `8ef03d7fd7557772e1b531b71b71c08e3419ff54`.
Its build phase remains **pilot**, with the original two-root workload,
preparation report and load/preparation/compaction timings unchanged. The later
[Root selection](../provenance/selected-fallback-two-root-cache/root-final-cache-selection.json)
chooses this complete file as the fallback; it does not relabel the pilot as a
new final build. `workload.json` retains the exact producer workload bytes.

Native compatibility is accepted for the actual C6 consumer
`c6dcc126bfaf0164870776e1018d08bdafb1e117` and frozen `f022` two-root workload,
using the [accepted semantic projection](../provenance/selected-fallback-two-root-cache/accepted-projection.json).
This does not establish compatibility with a newer cohort. The separate fresh
f022 attempt had ten successful cases, one deadline failure and two cases not
started; it is retained as incomplete evidence, not a complete thirteen-case pass.

The separate three-root final trial completed only one of three roots, captured
792,831 intermediates, and exhausted its time budget after 32,613.349550541956
seconds. It produced no final gzip candidate. No partial record from that trial
is distributed here; its [terminal outcome](../provenance/selected-fallback-two-root-cache/rejected-three-root-terminal-outcome.json)
is preserved without promotion.

Preparation uses strict unresolved rejection with advisory recorded entry
coverage and the complete-native-declared-terminals postcondition. Every stored
record carries the exact native guards. Cache completion neither widens recorded
entry predicates nor proves the declared terminals are a globally complete
known master basis. All 640 declared master coefficients remain uncomputed.

Selection relies on completion, size and accepted native compatibility, with
modest preliminary tuning/intermediate-use evidence. Final held-out and physical
cached-versus-uncached medians remain pending; no speed gain is guaranteed.

The [selection provenance](../provenance/selected-fallback-two-root-cache/SELECTED_FALLBACK_CACHE.json)
links the original producer, accepted consumer bridge, rejected trial and
unchanged historical pre-selection records. The optional source-evidence archive
declared by the root manifest is a separate historical audit download, not a
second runtime cache. Its [index](../provenance/cache-build-source-evidence.json)
documents original proof/workload hashes and relative-path reproduction inputs.
This source stage does not itself publish a release or change `data-latest`.
