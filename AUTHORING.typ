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

== Graph conventions and coverage

Five-loop maximal parent graphs come from the audited physical parent incidence
and momentum-routing data in `provenance/five_loop_data.rs`. Terminal graphs
contract absent physical edges and label surviving edges by their original
common-basis denominator and power. Numerator slots and the exact routing are
stored as graph attributes. The family graph is an atlas of all four maximal
physical parents; the complete fifteen-denominator family also contains
auxiliary slots and is not one fifteen-edge physical topology.

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

== Authoring and releases

The tooling needs Python 3.11 or newer and only its standard library. Generate
all loop manifests together after intentional data changes:

```sh
python3 tools/data.py generate --version v0.1.0
python3 tools/data.py validate
python3 -m unittest discover -s tests
python3 tools/data.py pack --output /absolute/workspace/releases/v0.1.0
```

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
