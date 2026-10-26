= Maintaining Vakint external data

== Data contract

The root `manifest.json` uses `vakint.external-data.v1`. Its version is an
immutable `vMAJOR.MINOR.PATCH` tag, and its `loop_packs` array lists disjoint loop
directories. Each record includes the loop manifest path and SHA-256, archive
name, and nullable archive SHA-256 and byte count. Source checkouts leave the
archive fields null. Release builds fill them after deterministic compression.

A loop manifest uses `vakint.external-data.loop.v1`. Its file inventory covers
every regular payload except the loop manifest itself; the root manifest checks
that file. All paths in a loop manifest are relative to its own directory.
Never resolve untrusted paths without rejecting escapes and symlinks.

Master identities combine the full family fingerprint and ordered powers. The
`files` map references unchanged `symbolic.json` and `numerical.json` arrays of
`[epsilon_power, expression_string]` pairs. `coefficients` records actual
per-power availability and validated significant digits. Exact symbolic
availability does not silently remove finite constants from an expression.
`available_epsilon_powers` is authoritative; legacy `epsilon_range` is provenance.

The original root artifacts, original topology source, and an exhaustive
migration receipt live in `provenance`. Do not rewrite those original records
when publishing new producer results. Add new provenance receipts and update
the generation tooling to select the new source explicitly.

`provenance/coefficient-supplement.json` records validated Laurent orders that
were available in authoritative master formulas but omitted from the original
export. It extends individual master identities with explicit per-coefficient
exactness and numerical precision. Original coefficient files are preserved in
`provenance/original-coefficients`, and migration receipt paths are retargeted to
those unchanged bytes. Each affected runtime loop pack includes its own slice
of the supplement receipt. The original manifest itself is never rewritten.

=== New accepted producer results

`provenance/producer-update.json` explicitly selects newer accepted results,
using `vakint.external-data.producer-update.v1`, a `provenance` object containing
the producer's source hashes and acceptance evidence, and a `masters` dictionary
keyed by the unchanged full `master_id`. Each value has a `coefficients` array:

```json
{
  "epsilon_power": 0,
  "symbolic": true,
  "numerical": true,
  "significant_digits": 200
}
```

Boolean capability fields are explicit. A numerical entry needs a positive
integer validated precision; a symbolic-only entry uses null precision. Do not
infer accuracy from string length or exactness from the presence of a string in
`symbolic.json`: that file also contains numerical fallbacks. An optional
entry-level `files` map uses the same loop-relative path and SHA-256 records as
the master manifest, binding the newly selected payload bytes. Other source and
evidence fields remain in the receipt.

Generation applies this cumulative selection after the immutable original
metadata and coefficient supplements. Updates replace capabilities only within
the original epsilon window; the existing 49 supplemented orders, with their
own precision and symbolic information, remain intact. Exact formulas must have
a symbolic payload, numerical flags must match actual rows, and a numerical-only
symbolic-file row must equal its numerical-file string. Every updated loop pack
receives its own `producer-update.json` slice, checked against its manifest by
validation. Stable names, full identities, aliases, graphs, IBPs and caches are
not recreated from the producer's directory names.

Preserve original coefficients and migration hashes before replacing payloads;
the original manifest and supplement receipts remain unchanged. Archive new
producer receipts under new evidence names, retaining earlier validation
archives. Exact relations containing independent period symbols remain symbolic
even when that period needs a separate evaluator or precision-limited data.
Native parser, period-resolution and numerical compatibility checks are distinct
from this metadata update; do not discard exact mathematics to pass them.

A source-tree update is not a release. An unreleased manifest version may be
committed and pushed without creating tags, uploading assets or changing
`data-latest`. Run the release workflow only when explicitly requested.

=== Validated numerical precision upgrades

Numerical precision upgrades are selected by
`provenance/numerical-precision-supplement.json`, after the original coefficient
supplements and producer update. Its loop slices authenticate both preserved
previous payloads and replacement files, and verify that every unselected
epsilon row stays unchanged. They cannot introduce orders or replace exact
formulas. An accepted exact-symbolic update can coexist with a numerical
precision upgrade only when its complete symbolic payload matches the preserved
upstream source. The coefficient records retain the validated digit limit separately
from stored digits, with a decimal `absolute_error` and `error_quality`.

The Bessel upgrade supplies PR4 and PR4d at epsilon orders zero and one with
20,000 validated digits and 20,008 stored digits. Its bounded absolute errors
include rounding to the published decimal center. Earlier producer receipts
remain unchanged; the new receipt explicitly supersedes their selected rows.
The PR11d finite coefficient now has the same 20,000 validated and 20,008 stored
digits for the three existing direct aliases P17, P52 and P74. Its positive
outward error includes published-center rounding. It remains numerical-only;
epsilon one retains its 200-digit capability and all negative exact-zero rows
remain unchanged. `PR11dep0` resolves this existing master coefficient and is
not an additional `constants.json` entry.

The cumulative supplement retains the original Bessel provenance unchanged.
Its optional `provenance.additional_sources` map declares the fixed PR11 source
adapter, and the three epsilon-zero selections carry its explicit `source_id`.
Selections without that field retain the legacy Bessel source. Unknown or unused
sources and duplicate authoritative rows are rejected. The PR11 before-images
and former complete supplement are preserved separately in
`provenance/numerical-precision-pr11d-before`.

The source-only `validation/pr11d-20000` bundle contains the immutable
`proof-index.json`, period, acceptance, scientific read-set and compressed proof
objects. Source validation runs the independently reviewed, fixed-SHA standard
library verifier; an `accepted` flag alone cannot admit data. It authenticates
both compressed and original bytes, replays the two final interval convolutions,
and checks the physical target, finite normalization equality and rounding cell.
The accepted scope retains 21 independently proved differential-equation rows
and 21 rows trusting the recorded external Kira derivation; the practical AMFlow
crosscheck is not a 20,000-digit certificate. These proof files stay outside loop
packs, whose loading continues to use authenticated coefficient bounds without
requiring the source validation directory or invoking a numerical engine.

The complete accepted Bessel proof archive is under `validation/bessel-20000`.
`python3 tools/verify_bessel_archive.py` checks its hashes using the standard
library. With `python-flint==0.9.0`, add `--replay-balls` to recheck the two
independent partitions, remainder bounds and exact reconstruction. Neither
command requires Mathematica or modifies accepted results. Archived Mathematica
sources and values document the independent development validation only.
For a replay of the original 98 recorded independent input comparisons, run
`validation/bessel-20000/portable_validate.py --output PATH` with a new directory
outside the archived bundle. Its original accepted verifier reproduces both
the payload and acceptance receipt byte for byte; `REPRODUCE.md` in that
preserved producer bundle documents its inputs and optional dependencies.

The original independent reference list included the unused point 15/16 instead
of the actual first shifted-interval center 1. It therefore covered 45 of the
46 required Taylor anchors. The sealed additive correction in
`validation/bessel-20000-anchor-one` supplies independent K0/K1 references at 1,
computed at 20,400 decimal digits and agreeing with Arb through 20,422 digits.
The original certificate, bounded Arb integration, public coefficient bytes,
and 20,000-digit capabilities remain unchanged. The precision supplement links
the correction explicitly, and validation checks the actual required point sets.
`validate_anchor_one.py` in the addendum replays this check without Mathematica;
run it in a copied development directory because it rewrites its local receipt.
The original portable replay alone does not include this additive check.

Snapshot-local finite primitive periods are recorded in an optional
`constants.json` per loop pack, authenticated both by `constant_bindings` and
the ordinary file inventory. Every record retains its exact definition,
validated precision, outward absolute error, and provenance. The source receipt
in `provenance/finite-constant-bindings.json` verifies that runtime records are
an exact schema projection of the accepted direct-moment payload. The sealed
high-guard integration and direct-moment export bundles under `validation/`
make those bounds independently replayable. Their larger internal precision
does not promote any public coefficient or primitive cap above 20,000 digits.

The additive `provenance/independent-d2-runtime-v1` selection supplies
`PR7D2`, `PR10D2` and `PR15D2` from independently defined convergent D2
integrals. Their 215-digit source caps are empirical refinement capabilities,
with `error_quality: "estimated"`; they are not interval certificates or
arbitrary-precision evaluators. The stored high-guard centers do not raise those
caps. `tools/d2_constants.py` authenticates the archived acceptance, validation
and profile inputs and reproduces the runtime schema projection using only the
standard library. It reads no D4 master coefficients and performs no new
numerical integration. PR10D2 and PR15D2 retain an error envelope covering both
accepted profile neighborhoods about the published center. Definitions use
positive Euclidean unit-mass conventions directly, with no extra Minkowski sign.

The finite-constant receipt's optional `additional_sources` selects this fixed
adapter. Unknown adapters, changed centers, errors, definitions or source caps
fail validation. Original four K5 records are retained exactly, and the former
runtime payload, receipt and manifests are preserved as byte-exact before-images.
The selected D2 values and their error metadata are carried in the ordinary
authenticated `4L/constants.json`; consumers do not execute the source verifier.

== Graph conventions and coverage

Five-loop maximal parent graphs come from the audited physical parent incidence
and momentum-routing data in `provenance/five_loop_data.rs`. Terminal graphs
contract absent physical edges and label surviving edges by their original
common-basis denominator and power. Numerator slots and the exact routing are
stored as graph attributes. The family graph is an atlas of all four maximal
physical parents; the complete fifteen-denominator family also contains
auxiliary slots and is not one fifteen-edge physical topology.

Every current five-loop terminal also declares `model: "model.json"`, bound by
the loop file inventory. Its `graph_definition.edge_powers` and
`graph_edge_to_family_slot` are projected from the native signed tuple and the
saved census witness, rather than inferred from a graph label. The graph loader
cross-checks these powers against the native diagram before returning a master.
`tools/replace_five_loop.py bind-graphs` upgrades these metadata bindings on a
current publication after verifying every existing DOT against its exact routing
witness and the unchanged scalar model. It does not regenerate payloads or use
the historical all-loop catalogue generator.

The additive `provenance/native-graph-identity-v2/migration.json` adapts the saved
DOTs to the maintained native FeynKit model and momentum notation. Model JSON
bytes remain unchanged. The two native model fingerprints changed because
neutral charge fields now serialize as exact rational strings, a scalar's absent
right-handed hypercharge serializes as null, and three exact formulas print in
canonical order. The preserved old/new model preimages and native proof identify
all six representation changes; no mass, coupling, interaction or ordering changes.

Only `model_fingerprint` and the saved DOT's `numerator`, `numerator_prefactor`
and `projector` attributes can change. The latter use the native parsed-expression
mapping from `FeynKit::Momentum`, `FeynKit::LoopMomentum` and
`FeynKit::ExternalMomentum` to `gammalooprs::Q`, `gammalooprs::K` and
`gammalooprs::P`, preserving every argument, representation and index. Native
inverse renaming is exact for all 147 changed expressions. The proof covers 755
external master graphs, their eight byte-identical family aliases and 41 additional
vendored checks. Old DOTs and historical migration/producer receipts are preserved.
The source validator replays only this fixed, authenticated projection; native
runtime loading still requires the current model fingerprint and tensor interface.
It does not enable a legacy fingerprint bypass or rewrite family/IBP identities.

Native closed artifacts own their root-domain certificates. Admission uses
`ClosedUnitMassProgram::validate_entry`, including both supported per-slot
root-power bounds and the total-excess scope. Neither predicate alone describes
the complete certified domain. Four-loop candidate
programs have pointwise guarded/descent checks, without an unrestricted closure
claim. Five-loop query predicates, owner transports, source scope and authority
remain in the original native publication. The bounds printed in its metadata
are not replacements for the recorded query predicates. Five-loop declared
terminals remain uncomputed, without a claim that the declared set is a complete
known master basis.

== Cache checks

The existing workload consists of physical parent pinches, at most two extra
positive powers and numerator rank at most one. Complete selected-root counts
are 5, 77, 2320 and 164352 for 1L through 4L. The validator checks completion,
payload hashes and native bundle binding identifiers. Vakint additionally must
cold-load the packs with its final RustRed dependency, compare guarded exact
results, and exercise prepared roots and intermediate hits before publication.
Do not substitute a checksum check for this native replay gate.

Keep optional intermediate-capture diagnostics. The existing four-loop receipt
records one capture-metadata exhaustion and 41790 skipped native records; all
selected roots are complete. Caches do not establish stronger IBP coverage.

Five-loop saved-application caches use one `cache/prepared.rrcache.gz` file and
`format: "rustred.saved-application-cache-file.v1"`. Its loop cache record carries
the native compressed/decoded BLAKE3 identity, decoded SHA256 and complete
semantic binding; the ordinary file inventory authenticates compressed SHA256.
`cache.json` uses `vakint.external-data.saved-cache.v1`, with `strict: true`, the
original `preparation_report`, authenticated `workload` path/SHA256, and final
build wall time including load, preparation and compaction. `tools/saved_cache.py`
checks the selected-root completion, disjoint held-out inputs, at most ten hours,
one gzip member, CRC, decoded size/hash and matching native framing. It reproduces
Vakint's field-length-prefixed semantic digest over the exact application bytes,
dimension, normalization, family fingerprints and signed catalogue identities.
Release labels, graph presentation and numerical coefficients do not enter it.

The native preparation profile must explicitly select `unresolved_policy:
"reject"`, `entry_coverage: "advisory"` and the
`complete-native-declared-terminals` root postcondition. Its canonical root list
records a boolean `coverage_admitted` separately. False coverage does not reject
a safely completed root or strengthen the saved campaign's certification. Any
unknown leaf still fails strict preparation; only complete, guarded native
records may be published or satisfy strict lookups.

The compressed file is limited to 95 MiB and decoded framing/payload to 1 GiB.
Above the 50 MiB target, `size_exception` must bind a measured comparison and show
at least twenty percent improvement in either the quadratic median IBP time or
the tuning-suite geometric mean against the best file at or below 50 MiB.
Native RustRed validation is separately required for BLAKE3, Symbolica state,
solver ownership, exact coefficients, guards and cold/warm parity. The Python
source checks never establish new algebraic authority or campaign coverage.

=== Optional cumulative NativePack transport

Large cumulative caches have an explicit, optional transport descriptor. They
preserve `cache/prepared.rrcache.gz`, its descriptor, size limits and provenance.
An explicitly requested official-data load selects the cumulative snapshot in
preference to that legacy small cache for the same loop count. Ordinary engine
construction remains offline. The cumulative NativePack has no total-cache size
cap. The 1.8 GB bound below admits individual release assets; it never authorizes
deleting, truncating or compacting records.

The root manifest's optional `runtime_cache_snapshots` list authenticates each
small descriptor with exactly `loop_count`, `manifest`, `manifest_sha256` and
`manifest_bytes`. Current source admission requires `loop_count: 5` and a path
`5L/cache/NAME.json`, also present in the five-loop file inventory. The same
descriptor bytes are published as standalone asset `NAME.json`; its immutable
release URL uses that basename. Descriptor basenames must be globally unique
across snapshot descriptors and release assets. At most one snapshot may be
selected per loop count; multiple same-loop rows are rejected, rather than
choosing the first. These are runtime assets, never `provenance_assets` evidence
declarations. The four-field reference schema remains unchanged.

`load_official_external_data(..., load_prepared_caches=True)` downloads and
attaches each selected snapshot automatically for the requested loop range;
`True` is the default. It authenticates the descriptor and parts against the
same release manifest before activating the complete dataset. With
`load_prepared_caches=False`, it still authenticates the selected descriptor,
but downloads no snapshot parts and attaches no prepared cache. An already
validated installation is reusable offline, including its selected snapshot.

A recognized external-data checkout never triggers HTTP requests or writes to
that checkout. For prepared-cache loading, its selected snapshot must already
exist at `cache-snapshots/DESCRIPTOR_SHA256`, relative to the checkout root,
where `DESCRIPTOR_SHA256` is the reference's `manifest_sha256`. A missing or
invalid local snapshot is an error, without falling back to the legacy small
cache or downloading parts into the checkout. Explicit import or manual cache
population is a separate operation. Setting `load_prepared_caches=False`
authenticates the descriptor without requiring this local snapshot.

Each descriptor uses `schema: "vakint.nativepack-transport.v1"` and exactly
`loop_count`, `binding`, `generation`, `stored_record_references`, `files` and
`parts`. The binding has the existing public Native fields: `artifact_digest`
(32 bytes), `family_fingerprint`, `physical_arity` and `layer`. Source validation
reproduces the active application's semantic binding. Native index decoding,
matching the declared generation/reference census and validating imported
records remain the consumer's existing Native APIs. Stored references are not
distinct keys, certified workload completion or a measured utility claim.

The `files` object maps exact paths to objects containing only `bytes` and
lowercase `sha256`. Allowed paths are `cache/bundle.rrindex`,
`cache/bindings/ID/cache.rrindex` and
`cache/bindings/ID/chunks/DIGEST.rrchunk.gz`; `ID` and `DIGEST` are 64 lowercase
hexadecimal characters. The packer treats all these files as opaque bytes.
The singular binding requires exactly one child namespace and its index; every
chunk belongs to that child. Native opening verifies the hashed namespace itself.
No locks, logs, job checkpoints or in-flight state enter the transport.
The source may retain Native's empty regular `writer.lock` at the bundle root or
binding child. Packaging omits that operational marker without modifying it;
nonempty markers are refused. This does not determine whether a writer is live:
the caller must supply an already sealed, independently validated snapshot.

Each ordered `parts` entry has exactly `kind`, `archive`, `archive_bytes`,
`archive_sha256`, `members`, and optionally `url`. Archive names are unique safe
basenames ending in `.tar.gz`; byte lengths are positive integers no greater
than 1,800,000,000. Members are sorted, unique exact file paths. Exactly one part
has `kind: "indexes"` and contains every index. All other parts have
`kind: "chunks"` and contain only whole chunk files. A global duplicate check
requires the disjoint member union to equal `files`, across all selected parts.

An optional HTTPS `url` locates an unchanged asset from an older immutable
release. Without it, remote transfer resolves `archive` beside the descriptor
URL. Offline import and producer checks always use `archive` beside the local
descriptor or in the explicit asset directory, ignoring `url`; no Python tool
fetches remote bytes. Full publication currently requires local verified copies
of every selected part, including reused assets.

`tools/data.py pack-nativepack` creates deterministic, separately checksummed
USTAR/gzip containers outside the preserved Native source. It partitions whole
files in lexical order, counts tar headers/padding/end blocks and reserves gzip
overhead before producing each part; the actual compressed length is checked
again. Metadata uses fixed modes, zero timestamps and uid/gid, empty user/group
names and gzip timestamp zero. An indivisible file that cannot fit is refused
without changing its bytes or discarding any record.

For an already preserved and independently validated Native snapshot:

```sh
python3 tools/data.py pack-nativepack \
  --source /workspace/preserved/native-bundle \
  --output /workspace/transport/parts \
  --descriptor /workspace/transport/snapshot.json \
  --binding /workspace/public-native-binding.json \
  --generation N --stored-record-references N
```

The binding JSON contains the public binding object itself. Generation and
reference census come from the authenticated Native snapshot, never a failed
job's completion label. For a later snapshot, add `--base-descriptor PATH` and
`--base-archives DIRECTORY`. The packer verifies and copies unchanged base chunk
parts byte for byte, adds containers only for novel chunks, and emits one fresh
index container. Old index containers are never overlaid. Earlier source files,
parts and descriptors remain intact; future same-binding mathematical merges
belong to Native validated append, not this transport.

After intentional admission, place the small descriptor in the loop inventory
and declare its authenticated root reference. Full `tools/data.py pack` requires
`--runtime-cache-assets DIRECTORY` containing exactly the selected part files,
alongside any required `--provenance-assets`. Packaging and publication both
stream-check every selected container, exact regular-file headers, member
bytes/SHA256, padding, gzip CRC and absence of trailing data. The complete
`SHA256SUMS` includes each unique part and standalone descriptor. The publisher
checks immutable committed metadata and retains the existing immutable-release
then alias-manifest-last sequence. Its 1,000-asset hosting allowance includes
standalone descriptors, the root manifest and checksums. No assets are uploaded
by packaging itself.

`--runtime-only` omits these optional external parts, retains their declarations
and small descriptors, records `omitted_runtime_cache_assets` and remains
explicitly nonpublishable. Compare independent tiny-fixture archive builds when
changing transport construction. Neither metadata nor container checks establish
new reduction identities; Native binding, guard, context and terminal validation
remain mandatory when a record is actually used.

CI packaging uses `tools/data.py pack --runtime-only --output PATH` to check
runtime archives without fetching optional source evidence. This explicit mode
requires an empty output directory, preserves the full manifest declarations
and runtime archive bytes, and writes checksummed `RUNTIME_ONLY.json`. These
artifacts are not a complete release and the publisher rejects them, even if
evidence is later copied alongside them. Full publication still requires the
default pack mode with every authenticated `--provenance-assets` file, using a
new output directory. Do not delete declarations or edit the manifest to make
an incomplete validation bundle appear publishable.

== Prepared physical benchmark inputs

`5L/benchmarks/quadratic` and `5L/benchmarks/zero-momentum` contain complete
saved scalar inputs for the native massless-QCD four-rung fixture. Each contains
only `prepared-input.json`, `vakint-input.symbolica` and
`projector-conditions.symbolica`. These are benchmark inputs, not reduction
caches or master coefficients. They are carried by the ordinary five-loop pack
and its authenticated file inventory.

The manifests retain the original generator source hashes, executable identity,
projection, complete nonzero conditions and historical preparation timings.
`benchmarks/provenance.json` connects them to the unchanged scientific acceptance
and validation receipts under `provenance/prepared-benchmark-inputs`. Recorded
development paths in those archived receipts are provenance, never paths that
runtime loading follows. The zero-momentum additive provenance distinguishes
the actual FeynKit owner revision from its feature base.

Vakint's `five_loop_qcd_ladder` example accepts `--prepared-input DIRECTORY`.
For the corresponding projection, it checks the exact scientific definition,
input and guard hashes and canonical symbolic identity before reuse. It also
reuses a valid saved bundle already present in its work directory. Input-loading
time is measured separately; the original preparation time is not reported as
current work. Use `--fresh-prepare` with a new work directory to validate native
graph, trace and Taylor construction independently. A corrupt or partial bundle
is an error and never silently triggers expensive regeneration.

For intentional additions, first prepare an external staging directory containing
only the accepted `benchmarks/` payloads and their small
`provenance/prepared-benchmark-inputs/` evidence. Scientific admission belongs to
the Vakint fixture loader and recorded generator checks; the following recipe
only installs those already accepted bytes using the existing data machinery.
Run it from a source checkout, preserving its release version. It changes only
the five-loop file inventory and the root's five-loop manifest hash, while
checking all prior payloads, lower-loop packs and the campaign semantic binding.
Do not use the historical `generate` command for this operation.

```sh
python3 - /absolute/workspace/accepted-loop-additions <<'PY'
from pathlib import Path
import json
import sys

sys.path.insert(0, "tools")
import data
from replace_five_loop import inventory, lower_snapshot
from saved_cache import semantic_digest

root = Path.cwd()
source = Path(sys.argv[1]).resolve()
if source.is_relative_to(root) or root.is_relative_to(source):
    raise ValueError("stage additions outside the repository")
release = data.validate(root)
directory = root / "5L"
manifest = data.read_json(directory / "manifest.json")
pack = next(row for row in release["loop_packs"] if row["loop_count"] == 5)
if pack["archive_sha256"] is not None or pack["archive_bytes"] is not None:
    raise ValueError("author a source checkout, never an installed release")
before = inventory(directory)
before.pop("manifest.json")
if before != manifest["files"]:
    raise ValueError("current loop payload inventory differs")
lower = lower_snapshot(root)
semantic = semantic_digest(directory, manifest)
additions = inventory(source)
if not additions:
    raise ValueError("no accepted benchmark additions selected")
for name in additions:
    if not name.startswith(("benchmarks/", "provenance/prepared-benchmark-inputs/")):
        raise ValueError(f"unexpected benchmark addition path: {name}")
for name in additions:
    data.copy_verified(
        data.checked_path(source, name), data.checked_path(directory, name)
    )
after = inventory(directory)
after.pop("manifest.json")
if any(after.get(name) != record for name, record in before.items()):
    raise ValueError("existing payload changed")
if any(after.get(name) != record for name, record in additions.items()):
    raise ValueError("copied additions differ from their selected bytes")
if semantic_digest(directory, manifest) != semantic:
    raise ValueError("campaign semantic binding changed")
manifest["files"] = after
data.write_json(directory / "manifest.json", manifest)
pack["manifest_sha256"] = data.digest(directory / "manifest.json")
data.write_json(root / "manifest.json", release)
if lower_snapshot(root) != lower:
    raise ValueError("lower-loop data changed")
data.validate(root)
print(json.dumps({
    "selected_files": len(additions),
    "selected_bytes": sum(row["bytes"] for row in additions.values()),
    "existing_five_loop_payloads_preserved": len(before),
    "semantic_digest_hex": bytes(semantic).hex(),
    "five_loop_manifest_sha256": pack["manifest_sha256"],
    "root_manifest_sha256": data.digest(root / "manifest.json"),
}))
PY
```

This source operation does not publish a release or attest to completed IBP
reductions. Final native API, reduction and cache checks remain required before
release publication.

== Authoring and releases

The tooling needs Python 3.11 or newer and only its standard library. Generate
all loop manifests together after intentional data changes:

```sh
python3 tools/data.py generate --version v0.1.0
python3 tools/data.py validate
python3 -m unittest discover -s tests
python3 tools/data.py pack --output /absolute/workspace/releases/v0.1.0
```

For a current five-loop publication, use `python3 tools/data.py set-version
--version vMAJOR.MINOR.PATCH` after completing intentional data changes. This
validates the checkout and changes only root/loop release identities and hashes,
preserving all accepted payloads and the current five-loop catalogue. Do not use
the historical all-loop `generate` command to replace a current publication.

The first migration additionally uses `tools/data.py migrate --source
/path/to/vakint/artifacts --vakint-source /path/to/vakint`. It refuses to replace
different existing data. Subsequent generations use the preserved provenance.

Archives use sorted USTAR entries, fixed metadata and gzip timestamp zero. Each
archive contains only its own loop directory, including its loop manifest. The
release manifest and `SHA256SUMS` are separate assets. Generated release archives
must remain outside the source repository. Compare two independent builds before
publishing a change to the compressor or packaging script.

After native validation and all repository checks, commit and push the source,
then run `python3 tools/publish.py /absolute/workspace/releases/v0.1.0` with an
authenticated GitHub CLI. This publishes a complete immutable release before
updating `data-latest`. Published immutable releases are never overwritten.
The latest alias receives version-named archives first and its manifest last;
previous version-named archives remain available for clients using an older
manifest. The alias tag itself is not an immutable data identity: use the
version recorded in its manifest.

Do not publish until Vakint's native compatibility and numerical checks pass.
The CI workflow validates and packages the repository but does not publish.

== Provenance and rights

The migrated native payloads and master coefficients retain their existing
provenance and citation requirements. Vakint is distributed under MIT; the
migration does not remove research-paper attribution or relicense third-party
software. Symbolica licensing applies to native loading/evaluation, not to this
Python-only checksum and packaging workflow. Never commit a license key.
