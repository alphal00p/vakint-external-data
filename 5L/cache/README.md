# Selected five-loop LIGHT cache

`prepared.rrcache.gz` is the exact user-frozen B candidate: 54 Route records and
2,048 Apply records, 2,102 strict-complete records in total. It is 89,635,796 bytes
compressed and 104,661,730 bytes decoded. Its compressed SHA-256 is
`708361954e61e853666d5bb637ad0d58a4336385d4bc9f23133d6ed7e3330021`.
It fits the official 95,000,000-byte LIGHT budget and default 1 GiB decoded bound.

The [user freeze](../../provenance/light-selection/frozen-B-20261028/selection-freeze.json)
accepts this existing validated candidate as adequate and ends selection/tuning.
It is not a performance-winner claim. The composed usage profile is
`041f4aa710909c28af60b9be68befd58a5a2f6d61662253610a5ff81ce2aa57f`,
bound to the original cumulative Native index `2658cd25…` and unchanged original
data/cohort receipts. Only positively observed tuning/physical inputs select
records; final held-out results were not used.

The [raw Native validation](../../provenance/light-selection/frozen-B-20261028/native-validation.json)
records exact selected/reimported/complete counts of 2,102, zero missing/partial
records, exact coefficients and original ordered guards, declared-terminal
validation, codec State 6, and unchanged source identity. Its standalone Native
`c2ca815` exporter and the measured Vakint `2d70bfe` collectors retain their actual
separate compiled cohorts. Portable source admission authenticates those proofs;
it does not make a new algebraic or performance claim.

`../cache.json` uses the existing usage-selected strict-snapshot schema, with
`coverage_claim: false`. All 640 terminal definitions, master graphs, IBP payloads
and empty coefficient maps remain unchanged, as do the lower-loop packs. Cache
records neither enlarge the published starting predicates nor compute master
values. Full HEAVY and useful raw prefixes remain independently preserved.

The former 2,456,235-byte two-root fallback, its workload/metadata, original
manifests and README were archived before replacement under
[`provenance/replaced-fallback-20261028`](../../provenance/replaced-fallback-20261028).
Its historical producer/consumer and failed-trial receipts remain unchanged.
The original five-loop noncache README is intentionally preserved as part of the
authenticated input-data snapshot; this file describes the current selection.
The existing version-bound source-evidence download remains separate from the
runtime cache. This source adoption does not publish a release or update
`data-latest`; see the [adoption record](../../provenance/light-selection/frozen-B-20261028/ADOPTION.typ).
