# Vakint external data

The branch `release/v0.4.0-prep` declares v0.4.0: the unreleased line that follows the
v0.3.0 release. There is no v0.4.0 release. For published, checksummed data, use the
v0.3.0 release or `data-latest`.

## v0.4.0: five-loop p-integral package (library 1-5) as a checksummed dataset

Release v0.4.0 ({{TO FILL FROM pins: pin.release_date}}) adds the five-loop p-integral package (a minor
release). Since v0.3.0:

- Five-loop p-integrals: the RustRed p library of scope 1-5 (`p-library-1-5`, package revision
  `{{TO FILL FROM revision: rev.revision}}`) for massless propagator integrals (p-integrals) with one to five loops. With it,
  Vakint reduces one- to five-loop p-integrals of the library's families with RustRed and expands them in ε with the
  five-loop master catalogue v4 (exact coefficients where they are known, `UNKNOWN(master, k)` where they are not: see
  Known limits). v0.3.0's p library (`p-library-1-4`) reaches four loops; it stays in the `p_integral/` area unchanged.
- The library: {{TO FILL FROM revision: rev.counts.classes}} owner classes over
  {{TO FILL FROM revision: rev.counts.tops}} top families and {{TO FILL FROM revision: rev.counts.sectors}}
  sectors; 266 named nodes, the caller families T002e ... T283 (129 five-loop, 88 four-loop, 39
  three-loop, 10 two-loop), each with its own stored owner table; {{TO FILL FROM revision: rev.residual_terminals}}
  residual terminals, which the catalogue maps onto masters (Known limits); the
  saved route verification `routes.rrbin`; the explicit key relations of node T266 (`relations/`).
- Not in this repository: the library is {{TO FILL FROM revision: rev.library_files}} files,
  {{TO FILL FROM revision: rev.library_bytes|gb}} (single files up to {{TO FILL FROM revision: rev.largest_bytes|gb}}, far above the
  100 MB per-file limit of the `p_integral/` area), so it is one compressed, checksummed dataset kept on the producing host,
  {{TO FILL FROM DATASET.json: ds.archive.bytes|gb}} in {{TO FILL FROM DATASET.json: ds.parts}} parts below 2 GiB. This
  repository records it in [`datasets/{{TO FILL FROM revision: rev.name}}/`](datasets/{{TO FILL FROM revision: rev.name}}/README.md):
  its checksums, the area manifest it restores (every library file with sha256 and size), the master catalogue and the
  restore commands. Nothing of it is in a release archive or a managed install.
- Changes since the last five-loop candidate (vk5l-s12349d-r2, 18 November 2026, never released), per node:
  {{TO FILL FROM notes/r3/RELEASE_NOTES_CONTENT.md section C at the freeze: pin.changes_since_r2}}
- Master catalogue v4 (`{{TO FILL FROM revision: catalogue.data_version}}`, sha256
  `{{TO FILL FROM revision: catalogue.sha256}}`): {{TO FILL FROM revision: catalogue.masters}} GGPPSS masters,
  {{TO FILL FROM revision: catalogue.placeholders}} placeholder masters, and the map of the package's residual terminals
  onto them, onto Forcer masters and onto Γ factors (Known limits).

{{TO FILL FROM tools/r3/package_content.py <final r3> --base <r2> (.short.md): include:content_short}}

- Obtain and restore. The dataset is the directory `{{TO FILL FROM DATASET.json: ds.location}}` on the producing host
  (`DATASET.json`, `SHA256SUMS`, `SHA256SUMS.files` and the parts `{{TO FILL FROM DATASET.json: ds.archive.name}}.part-000`,
  ...); copy that directory as it is. The parts' concatenation is the archive (sha256
  `{{TO FILL FROM DATASET.json: ds.archive.sha256}}`); it unpacks to `{{TO FILL FROM revision: rev.name}}/`, an overlay
  of a checkout of this repository at v0.4.0. In a fresh checkout:

  ```sh
  git clone https://github.com/alphal00p/vakint-external-data && cd vakint-external-data && git checkout v0.4.0
  D=/path/to/{{TO FILL FROM revision: rev.name}}            # the copied dataset directory
  (cd "$D" && sha256sum -c --ignore-missing SHA256SUMS)    # every part
  cat "$D"/{{TO FILL FROM DATASET.json: ds.archive.name}}.part-* | sha256sum   # = the archive sha256 above
  cat "$D"/{{TO FILL FROM DATASET.json: ds.archive.name}}.part-* | {{TO FILL FROM DATASET.json: ds.decompress}} | tar -xf - --strip-components=1 -C .
  sha256sum -c "$D"/SHA256SUMS.files                       # every restored file (paths relative to the checkout)
  ```

  Then load the checkout as a directory: `Vakint::load_external_data(<checkout>, n)` (Python:
  `engine.load_external_data("/path/to/vakint-external-data", max_loop_count=n)`, any n from 1 to 5: the p library is
  found through the same root; n decides which vacuum loop packs are loaded). Vakint checks every listed library file
  (sha256 and size) when it loads the library, says once on stderr that the listed library supersedes the built-in one,
  and ignores the unlisted `p_integral/p-library-1-4/` with one stderr line.
- Without a checkout: restore the dataset into an empty directory (`tar -xf -` without `--strip-components`)
  and set `VAKINT_P_LIBRARY=<dir>/{{TO FILL FROM revision: rev.name}}/p_integral/p-library-1-5` for the Vakint process:
  the library, its catalogue and its relations are then used directly, whatever external data are loaded (the variable
  comes first). In this mode Vakint does not check the files against the area manifest: run the `sha256sum -c` steps
  above first. Leave `VAKINT_P_LIBRARY_VERIFY` unset: a verified load needs `census.json` (1.47 GB), which the dataset
  does not carry.
- Compatibility: Vakint from gammaloop `p_integral` {{TO FILL FROM pins: pin.vakint}}, built with the
  five-loop feature, five-loop p families having 20 slots:
  `RUSTRED_RUNTIME_ARITIES=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,20 cargo build --features vakint/five-loop-p` (the
  default build compiles arities 1-16 and refuses a 20-slot chart). Its RustRed is {{TO FILL FROM pins (the rustred revision in that gammaloop's Cargo.lock): pin.vakint_rustred}};
  RustRed main {{TO FILL FROM pins: pin.rustred_main}}, RustRed `p_integral`
  {{TO FILL FROM pins: pin.rustred_p_integral}}. The library is bound to its RustRed by its identity
  (`p-library:scope=1-5:...,P_PACKAGE_REVISION={{TO FILL FROM revision: rev.revision}}`: scope and every `P_*` version
  constant): a build with other constants refuses it with one error ("the library ... is not the one its entry records").
- Older Vakint builds and this release: a managed install of v0.4.0 holds the loop packs only, identical in content to
  v0.3.0's, and loads in every build that read v0.3.0 (the release manifest schema is unchanged; the version is compared
  only with the requested one). A checkout of v0.4.0 without the dataset behaves as v0.3.0. With the dataset restored:
  builds without the `p_integral/` area (the `vakint_rustred` line) ignore it; gammaloop `p_integral` builds before
  72632d50f do not load the five-loop library: they read only master catalogues of schema `vakint.p-master-catalogue.v1`
  and stop with "schema vakint.p-master-catalogue.v2, this vakint reads vakint.p-master-catalogue.v1" (every p-integral
  of the library fails with that error; vacuum integrals are unaffected).
  {{TO FILL FROM notes/r3/LOAD_<final r3>.md (one run of the pinned Vakint on the final r3): pin.compat_final_r3}}
- This Vakint and older data: a managed install of v0.3.0 or earlier loads as before. A checkout of v0.3.0 gives the
  1L-4L p library `p-library-1-4` (its identity is the one this Vakint's RustRed computes for scope 1-4) and no
  five-loop p-integrals; the five-loop dataset needs a checkout of v0.4.0 (its root manifest carries v0.4.0's release
  identities: restored over a v0.3.0 checkout, every load stops with a loop-manifest SHA256 mismatch).

Known limits:

- Unknown master coefficients ship as `UNKNOWN(master, k)`. Catalogue v4 ({{TO FILL FROM catalogue: catalogue.data_version}},
  sha256 {{TO FILL FROM catalogue: catalogue.sha256}}) holds the 281 GGPPSS masters, each known exactly from its leading order
  through eps^k (masters per k: eps^0 68, eps^1 46, eps^2 63, eps^3 22, eps^4 24, eps^5 24, eps^6 13, eps^7 8, eps^8 5,
  eps^9 6, eps^10 1, eps^14 1). Its later orders through eps^12 are expected but not known: vakint writes them
  `UNKNOWN(<symbol>, k)` (e.g. `UNKNOWN(ggppss_int_53,7)`), except the dependent orders of the next item. From eps^13 on an
  order is an ALARM order, which no request is expected to need; ggppss_int(23), known through eps^14, has no UNKNOWN order
  and ALARM from eps^15.
- 39 of these orders, on 31 masters, are dependent: an exact part plus rational multiples of free `UNKNOWN` symbols. 38 are the
  dependences printed in GGPPSS's MasterExpansions.m. The 39th is an identity derived here by an IBP recurrence and checked on
  the printed orders: eps^6 of ggppss_int(74) = 18 x eps^7 of ggppss_int(53) + C, C exact. Two further identities of this kind
  (eps^6 of ggppss_int(88), eps^5 of ggppss_int(99)) are not used: those orders stay free.
- Of the package's 231 residual terminals, 222 map onto GGPPSS or Forcer masters and Γ factors and 9 onto placeholder masters
  `X(<node>:<key>)` without coefficients (one key with one dotted line in each of T266, T267, T270, T271, T273, T275, T276,
  T278 and T282): all their orders eps^-10..eps^12 are UNKNOWN (no five-loop massless propagator integral has a pole below
  eps^-10: at most one UV and one IR pole per loop).
- vakint (gammaloop `p_integral` {{TO FILL FROM pins: pin.vakint}}) carries `UNKNOWN` symbols exactly; they cancel only where
  their exact coefficient cancels. By default a result that still contains one is refused with `UnknownMasterCoefficients`
  (Python: `ValueError`); the pinned vakint prints, for the placeholder key of T278:

      {{TO FILL FROM notes/r3/LOAD_<rev>.md (strict-mode refusal on the T278 placeholder key, verbatim, at the final pin): pin.refusal_message}}

  With `allow_unknown_master_coefficients` (setting, Python keyword, or environment
  `VAKINT_ALLOW_UNKNOWN_MASTER_COEFFICIENTS=1`) the result keeps the symbols, and `Vakint::unknown_master_coefficients` lists
  them for callers that combine results. A needed ALARM order is always `MissingMasterOrders` (Python:
  `MissingMasterOrdersError`, a `ValueError`); Retain mode substitutes no masters. The catalogue is the package's
  `p-master-catalogue.json` (`VAKINT_P_MASTER_CATALOGUE=<file>|off` overrides it); without the five-loop package, vakint's
  built-in catalogue v3.2 has no UNKNOWN orders.
- Not workable with the current engine: the hardest five-loop reductions of the six-loop beta function (the 14-line top shapes,
  such as the (14,3,7) key of graph 630 and the box edge (4,7) that every node T265-T283 reaches) are estimated, as lower
  bounds, at about x100 or more the largest reduction finished so far (T278's (14,1,0) corner: 14.37 G operations, 8.5 h,
  174 GiB). More cores do not change this: the recording pass of one request runs on one core, so one such key needs weeks to
  months and tens of TB of trace. What could change it is fewer dots and ranks on the input side, or an engine that records
  without a full trace.
- Memory and time: the library loads lazily ({{TO FILL FROM notes/r3/LOAD_<rev>.md: pin.load_library}}; r2: 21-28 s, 5.7 GB).
  A process builds each large owner once, at its first use:
  - T162: {{TO FILL FROM notes/r3/LOAD_<rev>.md: pin.load_T162}} (r2: one key 56 s-2.4 min, peak 7.9-22 GB depending on the engine build);
  - T178: {{TO FILL FROM notes/r3/LOAD_<rev>.md: pin.load_T178}} (r2: one key 42-45 min, peak 7.4-8.9 GB);
  - T266: {{TO FILL FROM notes/r3/LOAD_<rev>.md: pin.load_T266}} (with r2's table the owner build peaked at up to about 106 GB,
    and the T266 acceptance key did not finish, see Acceptance).
  `census.json` (1.47 GB) is not shipped. Loading and reductions do not need it; only a verified load (descent certificate,
  `VAKINT_P_LIBRARY_VERIFY=1`) does, so that is not possible from the dataset alone. Do not add files to the shipped library
  directory: vakint then refuses it (unlisted file).
- Acceptance. Package r2's acceptance is provisional. 14 of its 15 checks passed: 11 file, layout and format checks;
  reductions of one light T162 integral and one light T178 integral, each identical to an earlier independent result; and
  one vakint evaluation through the released directory, identical to a value checked against an independent result to
  39 digits. The 15th check, one T266 integral served by the shipped relations, was stopped after repeated host-memory
  interruptions and has no result; it will not be resumed. Package r3 (`{{TO FILL FROM revision: rev.revision}}`):
  {{TO FILL FROM the Sunday acceptance record: pin.acceptance}}.
  r3's 15th check (the same kind of T266 integral, compared with a reference package) may finish after this release and
  does not block it; at the release: {{TO FILL FROM the stage-15 record: pin.acceptance_stage15}}. A judge verdict that fails
  only on the count of shipped-relation uses of a resumed final attempt, while the results of both packages have equal
  digests (and an earlier attempt counted at least one use), is recorded as a pass; the raw judge output and that ruling
  stand side by side:

      {{TO FILL FROM the stage-15 record (raw judge output, verbatim): pin.acceptance_stage15_raw_judge}}

  Ruling: {{TO FILL FROM the coordinator's ruling as applied to that output: pin.acceptance_stage15_ruling}}
- Evidence (never stated stronger than here):
  - {{TO FILL FROM catalogue: catalogue.terminals_placeholder}} of the {{TO FILL FROM catalogue: catalogue.terminals}}
    catalogued terminal integrals have no published value; they map onto placeholder masters whose coefficients are
    carried as UNKNOWN(master, k) for orders eps^{{TO FILL FROM catalogue: catalogue.placeholder_leading_order}} through
    eps^{{TO FILL FROM catalogue: catalogue.unknown_through}}. Published masters are known only through the order printed in
    arXiv:2104.08272; their later orders are UNKNOWN as well, and 38 printed linear dependences plus one derived identity
    tie some of them together. Strict mode refuses any result that still contains an UNKNOWN symbol; allow mode returns it
    with the symbol. The eps^{{TO FILL FROM catalogue: catalogue.placeholder_leading_order}} floor is an argument (at most
    one UV and one IR pole per loop), not a computation; the eps^{{TO FILL FROM catalogue: catalogue.unknown_through}}
    ceiling is a provisional limit, not shown to suffice for every six-loop use.
  - Ten catalogue rows (nodes T178, T182, T205, T222, T223, T238, T241, T255, T269, T277) were derived by this effort from
    its own five-loop reductions; at least nine of them by reconstruction from finite-field samples. The rows of T222 and
    T238 were reproduced by a second reduction on another package; for T255 an outside reviewer's value agrees at the
    order needed; for T178 a second integral of the same package gave identical terms. The other six were not reproduced
    by a second reduction. Ten further rows (T128e, T129e, T130p1, T131e, T132e, T133e, T135e, T140e, T142e, T144p5) come
    from one reduction each, reconstructed from finite-field samples, without a second route.
  - The changed tables were compared on a few integrals only. T180p2: two production integrals gave identical results on
    an earlier build sharing the records they pass through; three of its thirteen replaced records had not been passed by
    any production integral at writing ({{TO FILL FROM the pending T180p2 runs: pin.evidence_T180p2_pending}}). T162:
    identical results on four sets of integrals by sampled replay, on the table before its last three-piece replacement
    ({{TO FILL FROM the shipped T162 table's value check: pin.evidence_T162_shipped}}). T266 reduced table (if shipped):
    ten integrals checked against the values predicted by the graph's symmetry, on the full table with the symmetry file
    and a pre-release engine build, plus one integral on the reduced table
    ({{TO FILL FROM the T266 hand-in at its freeze: pin.evidence_T266_reduced}}). T266 changed relations (if shipped): no
    value comparison (operation counts on one integral). No changed table was re-checked on all reductions.
  - T167: one record is replaced by two pieces whose proof is an outside review's; this effort's own generator could not
    reproduce them. Value check: {{TO FILL FROM the two T167 identity runs: pin.evidence_T167_values}}.
  - The reduced T266 table (if shipped) omits records for integrals that the engine maps by a symmetry onto integrals kept
    in the table. It is complete only with rustred {{TO FILL FROM the gated engine at the T266 freeze: pin.rustred_symmetry_rule}}
    or later, which applies only such maps, and it must not load without its symmetry file:
    {{TO FILL FROM the refusal check on that commit: pin.symmetry_refusal_check}}.
  - Speed figures are per-record probes or partial runs (the T167 comparison stops before the end of the reduction); no
    end-to-end five-loop speed-up is claimed.
  - Checksums show that the files are the listed ones; they say nothing about the correctness of the reductions. vakint
    checks them at load; it does not verify the package's descent certificate, which is not part of the release. Descent
    (that each rule leads to simpler integrals) was re-checked only for the owners changed since the previous package; the
    rest is carried from the checked earlier package.
  - The T162 table, unchanged in its kept records since r2, contains a few records whose validity was checked on sampled
    integrals only ({{TO FILL FROM the shipped T162 table: pin.evidence_T162_sampled_records}}).
- Deferred (written up in the development notes, not part of v0.4.0): in the engine, a learned-denominator replay and a
  trace-free batched application. Abandoned: closed forms for the seven- and eight-line template recursions (estimated
  gain below x1.05). Not in r3: the size-reduced records of
  {{TO FILL FROM HANDINS.tsv at the content freeze (Sat 21 Nov, noon UTC): pin.size_reduced_not_in_r3}} (their base tables
  could not be reproduced); further T162 record replacements and drops (1355, 1522, 1903, five drops without whole-domain
  fallbacks) and the 1885 replacement; T282 2436 and the T265 packet; re-solved T266 K_a relations; symmetry files for
  other nodes; relations that avoid raising dots; unknown master coefficients beyond the published depth.

Every loop pack (1L-5L vacuum data) is that of v0.3.0; only the release identities change
(`tools/data.py set-version`: loop manifest versions, manifest hashes, archive names). The
`p_integral/` area is unchanged (the 1L-4L library `p-library-1-4` and its light cache).

A new managed install of `v0.4.0` or `data-latest` receives this release; `data-latest` moves to it. A managed install
holds the loop packs only: restore the five-loop dataset into a checkout of v0.4.0 (above).

## v0.3.0: five-loop basis BASIS-v3 with exact poles

Release v0.3.0 (17 November 2026) changes the five-loop master basis (a minor release) and makes every
five-loop pole coefficient exact. Since v0.2.3:

- 5L master basis BASIS-v3 (131 masters): As1-16359-0 (5L/P132), y-ent-3071-111011111201010
  (5L/P133), y-8175-num4_14 (5L/P134) and T1-8175 (5L/P135) replace the former masters
  P31, P108, P125 and P131. The 127 other masters keep their names, master_ids and values;
  names are stable (5L/provenance/display-names.json): the four former names are retired and
  never reused. The former masters are reduced like any other input (they are not published).
  The composed pack has no spurious d = 4 pole on any reduced top-sector integral.
- Poles: eps^-5..eps^-1 of all 131 masters are exact. 88 pole coefficients become exact in
  this release (2 at eps^-3, 24 at eps^-2, 62 at eps^-1): 79 from the R-operation with the overall counterterm by R*,
  5 from the R-operation without counterterm (omega < 0), 3 derived from the structural orders of
  the former masters, 1 by PSLQ with an R* counterterm check; each was checked against the
  numerical value it replaces (agreement within 1 digit of that value's claim). eps^-5..eps^-2
  use classical constants only; eps^-1 is exact in classical constants and 4L finite-part
  constants (49 of the new forms; 4L/constants.json).
- eps^0: 21 exact, 110 numerical. Published digit claims of numerical
  coefficients are the measured claim minus one digit (value strings rounded accordingly);
  exception: P132 at eps^0, P89 at eps^0:
  these two coefficients are quoted at their measured accuracy, without the safety digit;
  the smallest published claim is 32 digits.
- 5L/route-preparation.rrbin regenerated for the BASIS-v3 saved application.
- Traditional constants (documentation only): provenance/traditional-constants-v1 gives the
  constant names of this repository as exact expressions in traditional constants, the integral
  definitions of those that do not reduce, and an optional machine-readable rewrite table
  (D5bar3 undecided). No symbol or coefficient file changes; a later release may rewrite the
  3L/4L files in these constants and keep the old names as aliases.

Per order (5L, 131 masters): eps^-5: 0 78, S 53; eps^-4: 0 72, S 59; eps^-3: 0 60, S 71; eps^-2: 0 51, S 80; eps^-1: 0 28, S 33, S* 70; eps^0: N 110, S 6, S* 15.

A new managed install of `v0.3.0` or `data-latest` receives this release; `data-latest` moves to it.

## v0.2.3: five-loop values

For the five-loop data, release v0.2.3 (10 November 2026) updates 5 five-loop
coefficients of v0.2.2. Since v0.2.2:

- 5L/P68 (v0.2.0 P400) eps^0: 33 digits instead of 3.6 (provisional in v0.2.2), from the
  class-16359 high-precision grid.
- 5L/P85 (v0.2.0 P441) eps^0: 39.8 digits instead of 3.6 (provisional in v0.2.2), from
  the class-16359 high-precision grid.
- 5L/P89 (v0.2.0 P445) eps^0: 32.5 digits instead of 3.5 (provisional in v0.2.2), from
  the class-16359 high-precision grid.
- 5L/P125 (v0.2.0 P551) eps^0: 40.8 digits instead of 3.4 (provisional in v0.2.2), from
  the class-16359 high-precision grid.
- 5L/P130 (v0.2.0 P632) eps^0: 40.7 digits instead of 3.3 (provisional in v0.2.2), from
  the class-16359 high-precision grid.

Everything else in the five-loop data is unchanged: reduction tables, masters, graphs,
constants, exact coefficients, Ordered caches and every other five-loop numerical value
of v0.2.2.

A new managed install of `v0.2.3` or `data-latest` receives this release, as does an
existing one loaded with `version="v0.2.3"` or `refresh=True`. An existing `data-latest`
install moves to it with Vakint from gammaloop `vakint_rustred` 364ba0525 on, which
re-checks `data-latest` for `version="latest"`; older builds keep its cached release
(for example v0.2.2) until it is refreshed.

## v0.2.2

Release v0.2.2 (7 November 2026) is a data-only release: it updates one five-loop
coefficient of v0.2.1. Since v0.2.1:

- 5L/P88 (v0.2.0 P444) eps^0: 44.6 digits instead of 3.6 (provisional in v0.2.1), from
  the class-16119 high-precision grid.
- 5L, still provisional: 5 eps^0 coefficients ship numerically with their validated
  digits, 3.3-3.6 (eps^0 of 5L/P130, 5L/P125, 5L/P89, 5L/P68, 5L/P85); v0.2.3 (data
  only) will replace them (at least 16 digits, target 50).

Everything else is unchanged: all reduction tables, masters, graphs, constants, exact
coefficients and Ordered caches, and every other numerical value of v0.2.1.

A new managed install of `v0.2.2` or `data-latest` receives this release, as does an
existing one loaded with `version="v0.2.2"` or `refresh=True`. An existing `data-latest`
install moves to it with Vakint from gammaloop `vakint_rustred` 364ba0525 on, which
re-checks `data-latest` for `version="latest"`; older builds keep its cached release
(for example v0.2.1) until it is refreshed.

## p_integral area (branch `p_integral`, not released)

The branch `p_integral` adds a top-level `p_integral/` area for massless propagator
integrals (p-integrals) on top of v0.2.2. Every loop pack, table, master, constant and
Ordered cache is that of v0.2.2, unchanged; `manifest.json` gains only the key
`p_integral`. The area holds a light RustRed Ordered step cache of Vakint's built-in
1L-3L p library (`p_integral/ordered-cache/`, its metadata `p_integral/ordered-cache.json`
and the file checksums in `p_integral/manifest.json`). It is the complete cache of one
fixed workload, tuned to Vakint's p benchmark and test batteries rather than to physics
workloads: the 1L-3L benchmark grid, the 2L/3L physics cells, the Forcer batteries and
the anchors. Other inputs reuse only the sub-integrals they share with it. It was
recorded under exact, modular_polynomial and modular_sampled in turn (a modular
arithmetic visits a few steps exact does not) and serves all three without a miss. Vakint (gammaloop branch `p_integral`) uses it when these data
are loaded from a directory (`load_external_data`), and only if its directory name,
library identity, RustRed stamp and tail versions match the running build; otherwise
Vakint prints one line and reduces without it. Older Vakint builds and this
repository's other tools ignore the area. It is not part of any release: `tools/data.py
pack`, `tools/publish.py` and managed installs leave it out. `tools/p_integral_area.py`
stages and validates it (see AUTHORING.typ, "p-integral area").

The area may also hold RustRed p libraries (`p_integral/p-library-<a>-<b>/`, the output of
`rustred p-package`), each listed in `p_integral/manifest.json` `libraries` with its
directory, `P_LIBRARY_SCHEMA` (`schema`), scope, identity and the sha256 and size of each
of its files; Vakint builds that read the area adopt only a listed library of a schema
they support. Size rules (2026-11-08): every file of the area stays below 100,000,000
bytes (GitHub's limit), and a file above 50,000,000 bytes is compressed (`.gz`, `.zst`) or
split into `<name>.part-000`, `<name>.part-001`, ...; the light budget of 16,000,000 bytes
applies to the cache files (`p_integral/ordered-cache/`) only, and libraries have no
budget beyond the per-file rule.

## v0.2.1

Release v0.2.1 (6 November 2026) replaces the five-loop pack and adds one one-loop order. Since v0.2.0:

- 5L: a composed pack with 131 masters (111 previous campaign masters and 20 new
  integrals; what remains of the 640 terminals of v0.2.0 after a refinement layer of
  516 exact rows, `5L/provenance/refinement-layer.json`), chosen so that reduction
  coefficients have no spurious poles at d = 4
  (proven on the generators of the basis choice, rechecked on later reductions; the
  11-12-line top sectors are not validated). Every master ships its Laurent
  coefficients eps^-5..eps^0; `5L/producer-update.json` records how each order was
  obtained (exact product, structural zero, PSLQ form that passed the publication bar,
  or numerical value with its verified digits).
- 5L exact orders found by integer-relation search ship as exact only above the bar
  (excess >= 40 digits, blind re-discovery, no conflicting relation); 9 candidate forms
  below it ship as numbers.
- 5L: the trimmed Ordered step cache of v0.2.0 is removed (it belongs to the previous
  rule tables); `route-preparation.rrbin` is unchanged; the five-loop graph migration
  is recorded in `provenance/five-loop-graph-migration`.
- 1L: the tadpole gains its exact order eps^5.
- 5L, provisional: 6 eps^0 coefficients are still being computed and ship
  numerically with their validated digits, 3.3-3.6 (eps^0 of
  5L/P130, 5L/P125, 5L/P89, 5L/P68, 5L/P85, 5L/P88);
  v0.2.2 (data only) will replace them (at least 16 digits, target 50).
- 4L: 45 constants of `4L/constants.json` (the 41 non-built-in generators of the
  constant basis v4 and four dependent records) carry 2,348 to 19,997 significant
  digits instead of 520-650 (`provenance/precision-lift-4l-runtime-v4`). Seven of them
  (PR12D2Eps2/3, PR15D2Eps1-3, PR0D2Eps1/2; 2,348-2,805 digits) rest on two
  profiles of one code; four more (PR14ep2/3, PR5D2Eps4, D5bar3; 9,923-9,925
  digits) are confirmed by an independent implementation only to 5,060 digits;
  most of the others rest on rigorous balls of one code. Each record states how its
  digits were validated. Definitions are unchanged.

1L-4L reduction tables, masters, graphs, numerical values (apart from the tadpole's
eps^5 and the 4L constants above) and Ordered caches are unchanged. The pack was
composed with a patched RustRed binary (`5L/provenance/compose-binary`); it will be
recomposed once the upstream change is merged.

A new managed install of `v0.2.1` or `data-latest` receives this release, as does an
existing one loaded with `version="v0.2.1"` or `refresh=True`. An existing `data-latest`
install moves to it with Vakint from gammaloop `vakint_rustred` 364ba0525 on, which
re-checks `data-latest` for `version="latest"`; older builds keep its cached release
(for example v0.2.0) until it is refreshed.

## v0.2.0

Release v0.2.0 (2 November 2026) publishes the source updates of 28 October to
1 November 2026 described below; v0.1.2 stays available unchanged. Since v0.1.2:

- Exact 1L–4L coefficients: the last 43 four-loop numerical fallbacks have exact
  formulas, and every exact row is rewritten in the 68-constant basis v4
  ([`docs/basis.md`](docs/basis.md)). The rewrite leaves every numerical value
  unchanged. Rows with s6 write the Vakint built-in `vakint::s6`.
- Numerical 1L–4L values: 26 four-loop masters gained 500-digit windows, and 644
  rows of 112 three- and four-loop masters now hold the values of their exact
  formulas with more validated digits; `4L/constants.json` lifts five D=2 periods to
  520 digits and adds 41 constants.
- Caches: the depth-first prepared caches (1L–4L `cache/`, the 5L LIGHT cache) are
  retired. Each pack ships a RustRed Ordered step cache under `<L>L/ordered-cache/`
  (1L–4L complete, 5L trimmed to the release budget).
- 5L: the saved route-preparation add-on `5L/route-preparation.rrbin`.

Reduction tables, master sets, graphs and the five-loop catalogue are unchanged.
A new managed install of `v0.2.0` or `data-latest` receives the Ordered step caches
and the 5L route-preparation add-on, as does an existing one loaded with
`version="v0.2.0"` or `refresh=True`; an existing `data-latest` install keeps its
cached release (for example v0.1.2) until it is refreshed. v0.2.0 declares no
`provenance_assets`; the v0.1.2 cache-build evidence stays on the v0.1.2 release.

## Source updates

The 1 November 2026 source update retires the depth-first prepared caches and
prepares the packs for **Ordered step caches**. Vakint reduces only with RustRed's
ordered scheduler and never reads the depth-first caches any more; they are removed
from every pack (1L–4L `cache/` and `cache.json`, 9,867 files and 95.7 MB; the 5L
LIGHT `cache/prepared.rrcache.gz` with its README and `cache.json`, 89.6 MB), each
`cache` manifest section becomes `{"available": false}`, and
[`provenance/retired-dfs-caches-v1`](provenance/retired-dfs-caches-v1) records every
removed file and section (the bytes remain in Git history). A pack may ship one
RustRed Ordered step-cache directory per reduction program,
`<L>L/ordered-cache/<label>.<tables16>.<stamp16>/`, described by
`<L>L/ordered-cache.json` and the loop manifest's `ordered_cache` section. A cache
records checked Ordered steps (children with exact step coefficients, emitted
terminals and nonzero conditions in order; never weights or results), so results are
identical with and without it. It is bound by versioning only: its stamp covers the
RustRed step-cache schema, the step semantics version and cheap identity fields of
the program, and its directory name carries the program's rule-table identity.
Vakint uses a shipped cache only if both match the running build and the loaded
tables and every file matches the loop manifest; otherwise it prints one line and
runs that program without it. The 5L pack also ships `route-preparation.rrbin`, the
saved route verification of the 5L application, which RustRed restores instead of
re-verifying every transport route at load (rejected loudly and recomputed on any
mismatch). See [AUTHORING.typ](AUTHORING.typ) ("Ordered step caches"). Reduction
tables, masters, constants, graphs, numerical data and the 5L benchmarks are
unchanged.

The shipped Ordered step caches were written with the final RustRed main candidate
(step-cache schema `rustred.ordered-step-cache.v3`, step semantics
`rustred-ordered-steps-2026-10-31`, tail tables `rustred.ordered-tail.v3`; fewest-terms
Route layering and the adjoint tail, both RustRed defaults) by Vakint's
`ordered_cache_maintenance prepare`. Their workload is the 1L–4L zero-momentum and
quadratic ladder rungs, the four-loop benchmark integrals and the two 5L benchmarks:

| Pack | Programs | Records | Shard bytes | Tail bytes | Complete |
|---|---|---:|---:|---:|---|
| 1L | `1L-unit-mass-vacuum-k1` | 4 | 226 | 0 | yes |
| 2L | `2L-unit-mass-vacuum-k3` | 20 | 813 | 0 | yes |
| 3L | `3L-unit-mass-vacuum-k6` | 758 | 37,141 | 0 | yes |
| 4L | `4L-four-loop-{bmw,fg,h,x}` | 126,614 | 11,265,099 | 1,411,418 | yes |
| 5L | `5L-tide-five-loop-common-basis` | 1,082,534 | 94,257,265 | 0 | no (trimmed) |

The whole `5L/ordered-cache` directory with its metadata stays within the 95,000,000-byte
budget. It holds the 5L zero-momentum benchmark's step records (except one support-5
route shard that saved no time), and nine of its 31 shards also hold the 5L quadratic
benchmark's records. Every shard was chosen by the measured warm time it saves per byte
(`trim` in `5L/ordered-cache.json`). It ships no tail table: the zero-momentum tail table
speeds up that benchmark but slowed the quadratic one. The complete 5L cache (both
benchmarks: 2,142,618 records, 213.7 MB of shards and a 251.4 MB tail table) is
distributed separately; to use it, place its directory unchanged in a Vakint Ordered
cache directory.

The 31 October 2026 source update rewrites every exact 1L–4L coefficient row (739 rows
of 115 masters, 713 distinct coefficients) in one basis of 68 constants, with common
factors pulled out and terms collected; see [`docs/basis.md`](docs/basis.md). The
generators are pi, zeta(3), zeta(5), zeta(7), log 2, Li4/5/6(1/2), the alternating Euler
sum s6 (the Vakint built-in `vakint::s6`), log 3, Cl2(pi/3), Cl4(pi/3), Im Li3(i/sqrt3),
Im Li4(i/sqrt3), four sixth-root GPLs, the MATAD constants D5bar1/2, D6bar1/2 and
T111bar4, ten Bessel moments and jets, 30 D=2-2delta periods, and five weight-7 or D=4-2eps constants; `3^(1/2)` is an explicit
parity factor. The coefficients shrink from 20,971 to 6,645 terms. Each new row equals its
previous row once the identities listed in the publication receipt are applied. Most are
published reduction tables or proved identities. Some are numerical identities, not proofs:
the 48-term relation R1 among the D=2 jets, which removes `PR11dD2Eps2` (identical to
relation (c30) of arXiv:1609.05071 where comparable, verified to 547 digits); the two
identities that replace Im G(0,1,-omega) and Im G(0,1,1,-omega) by Im Li3(i/sqrt3) and
Im Li4(i/sqrt3) (4,100 digits); and the earlier BNbar4 and Li3(i/sqrt3) reductions and
the closed formula of `PR11dep0` (544 digits). Integer-relation searches at about 500 digits for
the hard constants and 5,000 for the classical ones find no other stable relation among
the generators or the products that occur. Possible jet-3 and jet-4 analogues of R1 are
not excluded at the available precision. Rows no longer use the coefficient aliases
`PR11dep0`, `PR4fin` and `PR4dfin`, the derived MATAD constants `S2`, `T1ep`, `T1ep2` and
`BNbar4`, the HPL words, or `PR10D2`, `PR15D2`, `PR5D2Eps3` and `PR11dD2Eps2`, whose
`4L/constants.json` records stay unchanged. Every row with s6 writes the built-in
`vakint::s6`, so three-loop loads evaluate it too; the four-loop record `s6weak` holds
the same number, stays unchanged, and no formula uses it. `PR12D2Eps3` is now validated:
its closure-implied control of at least 421 digits was accepted. Every `numerical.json`,
numerical precision record and constant value is unchanged, as is the five-loop data. See
[`provenance/takeover-basis-v4-rewrite-v1`](provenance/takeover-basis-v4-rewrite-v1).

A second 30 October 2026 source update replaces the numerical values of 644 of the
739 lower-loop coefficient rows (112 three- and four-loop masters) by the values of
their published exact formulas. Each formula was evaluated at 20,100 and 20,200
working digits, and a row was replaced only where the formula supports more validated
digits than the stored value and the two agree within their combined errors. 585 rows
now have 20,000 validated digits (3L 250, 4L 335). 59 four-loop rows whose formulas
contain D=2 periods, `K5MomentTaylor` or MATAD constants now have 516 to 520 digits,
limited by the validated digits of those constants. The other 95 rows keep their bytes:
the 1L and 2L rows are already at 20,000 digits, 57 rows are exact zeros, and PR4/PR4d
at epsilon zero and one and PR11d at epsilon zero keep their bounded 20,000-digit values.
The new errors are first-order estimates (`error_quality` `"estimated"`), not interval
proofs. Exact formulas, constants and the five-loop data are unchanged. See
[`provenance/symbolic-expression-evaluation-v1`](provenance/symbolic-expression-evaluation-v1).

The first 30 October 2026 source update closes the four-loop window: the 43 coefficients
that were numerical fallbacks now have exact formulas, so all 444 coefficients
(epsilon^-4 through epsilon^1) of the 74 four-loop masters are symbolic. The new
formulas use known constants and named D=2-2delta periods, D=4-2eps master
coefficients and MATAD constants installed in `4L/constants.json` with 520 to 650
validated digits (`s6weak`: 20,000). Each formula reproduces the independent
500-digit numerical values of its masters. Every constant record now also carries a
`symbolic_definition`, a Symbolica atom of its defining integral. Numerical values,
their precision and the five-loop publication are unchanged. This source update
creates no new release and does not change `data-latest`.

The 28 October 2026 source update gave all six coefficients of 26 selected
four-loop masters at least 500 validated digits; the three PR11d finite aliases
retain their stronger 20,000-digit values and bounded evidence.

Versioned native RustRed reductions, master-integral Laurent coefficients and
graphs, and Ordered step caches for
[Vakint](https://github.com/alphal00p/gammaloop/tree/vakint_rustred/crates/vakint).
The data originates in Vakint's former `artifacts` directory. Original lower-loop
payloads and migration checksums are retained; previous five-loop publications
remain available through Git history.

Each release has separate `1L` through `5L` compressed packs. Loading a maximum
loop count installs all packs up to that count. `data-latest` points to the
current immutable release through its `manifest.json`; exact versions remain
available independently.

An immutable release may also declare optional source evidence in the root
manifest's `provenance_assets` list. Each row contains `archive`,
`archive_sha256`, and `archive_bytes`: a versioned filename such as
`vakint-external-data-v0.1.2-cache-build-evidence.tar.gz`, its lowercase SHA-256,
and a positive byte length strictly below 2,000,000,000. Keep these large files
outside Git. They are evidence downloads, not runtime caches or loop packs.
Every release archive, including each loop pack, must satisfy that size bound.

After finalizing the release version and committing those static metadata rows,
place exactly the declared regular files in a separate directory and run:

```sh
python3 tools/data.py pack --output /path/to/release --provenance-assets /path/to/evidence
python3 tools/publish.py /path/to/release
```

Packing verifies and copies the files and includes them in `SHA256SUMS`.
Publication verifies the same committed metadata and all asset identities before
any release mutation, publishes the immutable assets first, and updates the
alias manifest last. Older versioned assets remain available through the alias.
Without `provenance_assets`, the existing packing and publication behavior is
unchanged and the extra argument is unnecessary. Version changes require
removing the old version's evidence rows and authoring the new ones explicitly.

CI can validate the same deterministic runtime packs without downloading source
evidence by running `python3 tools/data.py pack --runtime-only --output PATH`
with an empty output directory. This preserves the release manifest and runtime
archive bytes, records omitted evidence in checksummed `RUNTIME_ONLY.json`, and
produces **nonpublishable** validation artifacts. The publisher rejects them;
build a full release in a new directory with every declared source asset.

```python
engine.load_official_external_data(4)
engine.load_official_external_data(4, version="v0.2.1", local_artifacts_path="/path/to/data")
```

A checkout of this repository can be passed directly as `local_artifacts_path`
and is validated without network access. Source manifests leave archive hashes
unset; release manifests contain them. All loop-manifest paths are relative to
their loop directory.

1L–4L contain 115 computed masters in total. The 131 5L masters
(what remains of the 640 terminals of v0.2.0 after the refinement layer) have graphs,
exact identities and Laurent coefficients eps^-5..eps^0.
The five-loop graph files retain the complete numerator, propagator powers,
mass terms and explicit loop-momentum basis. Their names `P1` through `P131`
are assigned anew for each publication; match integrals by their family-qualified
signed index tuples, not by names from older releases. Ordered step caches
(`<L>L/ordered-cache/`, described by `<L>L/ordered-cache.json`) record the checked
steps of RustRed's ordered scheduler for a deterministic workload. They supply no
epsilon coefficients and do not certify IBP coverage; see `coverage.json` in each
pack.

The current five-loop source is recorded in
[`5L/provenance/current-publication.json`](5L/provenance/current-publication.json),
and its admitted starting queries remain in the native application package.
The rank and power-difference maxima summarize those predicates; they do not
assert coverage of every index tuple below the maxima. Historical records under
`provenance/original-root` are immutable migration evidence and do not define the
current five-loop basis.

Release v0.2.1 ships this five-loop source in its 5L pack. A checkout can also be
loaded directly:

```python
engine.load_external_data("/path/to/vakint-external-data", max_loop_count=5)
```

From v0.2.1 on the five-loop masters carry Laurent coefficients (eps^-5..eps^0).
Release v0.1.2 also shipped a selected 5L LIGHT depth-first cache of
2,102 records with Native `c2ca815` export/reimport validation, selected from
frozen tuning and physical inputs; it was retired with the other depth-first
caches (see the 1 November 2026 update above). Its selection evidence remains
under [`provenance/light-selection`](provenance/light-selection). The two-root
fallback it replaced, with its producer/consumer evidence and original manifests,
is preserved under
[`provenance/replaced-fallback-20261028`](provenance/replaced-fallback-20261028).
All five-loop non-cache files remain the unchanged input-data authority.

For a subsequent five-loop refresh, use `tools/replace_five_loop.py stage` with
the exported native application and its native terminal definitions, validate
the staged pack, and then use its explicit `install` command with an external
backup directory. This preserves all 1L–4L payloads and their root-manifest
entries. The historical all-loop `tools/data.py generate` command refuses to
overwrite a current five-loop publication. Staging and installing a source
update do not publish a GitHub release or change `data-latest`.

The lower-loop data contains 739 numerical coefficient rows: 739 have exact
symbolic expressions and 0 retain numerical fallbacks. These counts include
49 additional orders preserved from the previous export.
The six-coefficient windows have 20,000 validated digits at 1L and 2L. Every
nonzero three-loop coefficient now has 20,000 validated digits; the two exact-zero
rows of D6 keep their 2,000-digit entries. At 4L, every nonzero coefficient has at
least 516 digits: 34 windows have 20,000 digits in every row, 6 more in every nonzero
row (their exact zeros keep 200 or 500-digit entries), and the other 34 contain rows
at 516 to 520 digits. These values are
evaluations of the exact formulas, with estimated errors (publication
`symbolic-expression-evaluation-v1`). PR4/PR4d at epsilon zero and one, and PR11d at
epsilon zero, retain their 20,000-digit values and bounded errors. The 28 October
500-digit evidence used independent numerical refinements through 520 digits; it
remains the validation data of the formulas and is not an interval proof.
Per-coefficient limits remain authoritative; exact formulas can support greater
precision subject to the finite periods they contain.
An [additive oracle correction](validation/bessel-20000-anchor-one/coverage-correction.json)
supplies the missing reference at the actual integration anchor 1; the original
certificates and public numerical values are preserved unchanged.
Per-coefficient manifest entries record the actual precision, including the
separately validated extra orders.
Some exact expressions require the corresponding Vakint period evaluator;
symbolic availability alone does not imply unlimited numerical precision.
The 24 newly accepted PR4-family coefficients preserve the upstream exact
`vakint::K5Moment` and `vakint::K5LogMoment` formulas. Their four primitive
bindings in `4L/constants.json` carry independently integrated, bounded
20,000-digit values; the logarithmic moments include the factor three and
the `EulerGamma-log(2)` shift. These are finite capabilities, not arbitrary
precision evaluators. The independent symbolic and numerical payloads retain
their own availability and provenance.
PR11dep0 and its three direct master aliases share one authenticated finite
payload. Two bounded production profiles and two isolated standard-library
verifier runs certify its 20,000 validated digits and 20,008 stored digits.
The [portable proof index](validation/pr11d-20000/proof-index.json) and
[validation report](validation/pr11d-20000-reports/PR11D_VALIDATION_REPORT_FINAL.md)
record the normalization, error bound, and scope of the independent evidence.
Large proof objects are source-only evidence outside the downloadable loop packs;
loading or using Vakint does not execute their verifier or require Mathematica.

The PR14 epsilon-one formulas use `vakint::GPLReal`/`vakint::GPLImag` components
supported by the updated Vakint/Symbolica evaluator. Independent 400-digit
component references and a separate 20,000-digit bounded-kernel validation
accompany their qualification.

The four PR7 epsilon-one expressions are direct analytic dimensional-shift
results, validated against their own 200-digit numerical coefficients. The
independent D2 integral `vakint::PR7D2` is documented in
`4L/provenance/PR7-v23/independent-D2-period.json`; its 215-digit RustFlow
validation uses an empirical refinement model, with an independent
Mathematica check at 50 digits. The additive runtime projection now supplies
this independently defined period as a finite 215-digit binding with an
explicitly estimated error. It preserves all existing numerical precision
upgrades and the four bounded 20,000-digit constant bindings.

Run `python3 tools/data.py validate` to verify payloads, coefficient availability,
Ordered cache inventories and migration hashes. Release and authorship
instructions are in [AUTHORING.typ](AUTHORING.typ).

The eleven PR10/PR9d/combination-B finite expressions are direct analytic results,
independently checked against their own 200-digit numerical coefficients.
Their positive Euclidean D2 periods `vakint::PR10D2` and `vakint::PR15D2`
are defined in `4L/provenance/PR10-PR15-v24/independent-D2-periods-v1.json`,
with independent 215-digit empirical evidence. The additive runtime projection
supplies these positive Euclidean periods as finite 215-digit bindings with
estimated errors covering both accepted profile neighborhoods. These are not
interval certificates or arbitrary-precision evaluators. Every existing
numerical coefficient, extra order and bounded constant record is preserved.
The reproducible projection and exact before-images are under
[`provenance/independent-d2-runtime-v1`](provenance/independent-d2-runtime-v1).
This source update does not itself create a release.

The four PR10 epsilon-one expressions are direct dimensional-recurrence results,
independently checked against their own 200-digit numerical coefficients.
The initial 22-entry PSLQ search was unstable. After exact known-lower
subtraction, Symbolica and Mathematica recovered the five-entry residual
relation [8,189,27,-274,-30] at 100/110 effective digits, using 140/150
digits of the original targets. A separately constructed native full Atom
is exactly identical to the accepted dimensional-recurrence expression,
binding this recurrence-assisted recognition to the existing 200-digit
checks. This does not claim blind full-coefficient discovery.
The positive Euclidean D2 Taylor coefficients `vakint::PR10D2`,
`vakint::PR10D2Eps1`, `vakint::PR7D2` and `vakint::PR7D2Eps1` are defined in
`4L/provenance/PR10-epsilon1-v25/independent-D2-Taylor01-period-registry-v2.json`,
with independent 215-digit empirical evidence. Existing leading definitions,
all numerical precision, extra orders and bounded constant payloads remain
unchanged. This producer update adds no numerical binding by itself; runtime bindings
are managed separately by the authenticated projection. It creates no release.

The additive Taylor runtime projection supplies only `vakint::PR10D2Eps1`
and `vakint::PR7D2Eps1` as finite 215-digit bindings. Their estimated absolute
errors cover both accepted full profile neighborhoods around the chosen
high-precision center; they remain empirical, not interval bounds. The portable
full source records, reproducible projection, exact-arithmetic review and
seven unchanged previous bindings are recorded under
[`provenance/independent-d2-taylor01-runtime-v2`](provenance/independent-d2-taylor01-runtime-v2).
The source cap stays at 215 digits despite longer stored decimals. No producer
record, numerical coefficient or existing bounded constant binding is changed.

The 30 October 2026 four-loop closures (publication
[`provenance/takeover-4L-closures-v1`](provenance/takeover-4L-closures-v1)) give the
last 43 four-loop coefficients exact formulas. They cover 17 distinct directions of
the PR9, PR9d, PR15, PR11, PR11d, PR12 and PR0 masters and their alias combinations
on 26 masters. Each formula is an exact composition of accepted dimension-shift and
DREAM maps with named periods. The new periods are positive-Euclidean D=2-2delta Taylor
coefficients `vakint::<X>D2Eps<k>` of the hat integrals
X_hat(delta) = exp(4 EulerGamma delta) int prod d^Dk/pi^(D/2) prod 1/(q^2+1)^a, with
D = 2-2delta. They are complemented by the DREAM banana coefficients
`vakint::K5MomentTaylor(k,j)`, the D=4-2eps coefficients `vakint::PR14ep2`/`PR14ep3`
of master P31, the MATAD weight-7 constants `vakint::T111bar5`, `BNbar5`, `D5bar3`
and the alternating Euler sum `vakint::s6weak`. Their definitions and evidence are in
`4L/provenance/takeover-4L-closures-v1/independent-D2-period-registry-v3.json`.
Every formula agrees with the independent 500-digit numerical values of all its
masters to within 0.483 units of the last stored digit, and with the raw numerical
profiles to 543.6 to 548.1 digits. Its recorded symbolic cap is the minimum of its
constants' digits and its first-order statement budget (516 to 519 digits).
The constants carry estimated, empirical two-profile errors, not interval proofs;
each error includes the rounding of the stored decimal (one unit of its last digit).
Every constant has an independent-method control, except `PR12D2Eps3`. Under the rule
that such a control only has to catch systematic errors (30-50 digits suffice),
`PR10D2Eps4` has one at 139.35 digits and `PR14ep3` at 424.0 digits. `PR12D2Eps3`
has two-profile validation at 520 digits; its only control is implied by the P70
epsilon-one closure itself (at least 421 digits, an inference), so that formula
remains conditional on its label. `PR5D2Eps3` stays a numerical period here; its
exact formula belongs to the later rewrite in an independent constant basis.
Every `symbolic_definition` writes out its defining integral and each normalisation
factor (measure, signs, exponential and Gamma factors, Taylor coefficient, unit
mass); none refers to another named constant. The numerical rows remain
the validation data and are unchanged, as are all numerical precisions. P17/P52/P74
at epsilon zero keep their bounded 20,000-digit values next to the new exact row.
P19/P73 at epsilon zero keep their `PR11dep0` formulas.

The finite-constant adapter `takeover-4l-closures-v3`
([`provenance/takeover-4l-closures-runtime-v3`](provenance/takeover-4l-closures-runtime-v3))
lifts `PR7D2`, `PR7D2Eps1`, `PR10D2`, `PR10D2Eps1` and `PR15D2` from 215 to 520
validated digits and adds 41 constants. The superseded 215-digit projections still
replay unchanged against the archived before-image. Each `constants.json` record may
carry an optional `symbolic_definition`, a Symbolica atom of the defining integral.
It uses the inert heads `vakint::Integral(f, vakint::Interval(x,a,b), ...)` (first
interval outermost), `vakint::LoopIntegral(D, f, vakint::k(1), ...)` (Euclidean,
measure d^Dk/pi^(D/2) per loop), `vakint::SeriesCoefficient(f, x, x0, n)` (the
coefficient of (x-x0)^n) and `vakint::EuclideanDot`. The prose `definition` is unchanged.
`PR10D2`, `PR10D2Eps1` and `PR15D2` keep their producer routing in the metadata; their
`symbolic_definition` uses the routing shared by the other Taylor coefficients of the same
integral, and the metadata records the exact loop-momentum substitution between the two.
