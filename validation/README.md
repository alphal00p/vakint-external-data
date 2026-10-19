# Numerical migration evidence

These deterministic gzip files preserve the 464 legacy HPL projection values,
the 200- and 20,000-digit comparison results, all 324 computed complex words,
independent GiNaC checks, and shared-constant validation. They are development
reference material and are excluded from runtime loop packs.

The coefficient supplements add 49 previously omitted, known Laurent
coefficients: 25 at two and three loops and 24 at four loops. Their exporters,
verification reports and exact master-formula source inputs are archived here
as well; all old coefficient rows were checked before the new rows were
appended. The four-loop audit inventories every existing FMFT coefficient key
and records the graph factorizations used for the added orders. The serialization
report verifies all 49 appended symbolic expressions parse and round-trip using
explicit ASCII multiplication and exponentiation.

The producer provenance archive verifies all 52 masters containing the 104
numerical-only four-loop coefficients against their original accepted 50- or
200-digit receipts. Every acceptance hash matches the exported manifest, and
every accepted computed file is byte-identical to the runtime numerical file.
For example, PR4d's epsilon coefficient has independently refined 50-digit data
with a 70-digit internal comparison; the old FORM literal contains only 29
digits. Those additional digits are not obtained by resizing the old literal.

The separate legacy-source audit checks all 104 opaque rows: 89 are consistent
with the available FORM constants within their explicit precision and literal
rounding bounds, while 15 orders are absent from that older table. This audit
does not claim that the older table validates the additional producer digits.
The acceptance receipts supply that evidence. Historical FORM reference checks
remain unchanged; reduction comparisons with the newer data use FORM's exact
retained reduction and the same external coefficient inputs.

`manifest.json` checksums compressed and original bytes. The validator source,
dependency lockfile and original parallel coordinator are retained as execution
provenance; their original local paths must be adjusted when reproducing the run.
The Symbolica source revision is recorded explicitly. No license value or
Mathematica dependency is included.

The shared-constant report distinguishes agreement with a rounded source literal
from a strict relative-error target. Preserve those distinctions when replacing
finite tables with exact algorithms. Regenerate this archive with
`python3 tools/archive_validation.py VALIDATION_DIRECTORY --validator-source VALIDATOR_CRATE --symbolica-revision COMMIT --vakint-source VAKINT_CRATE`.

Archive the immutable original producer evidence with
`python3 tools/archive_producer_provenance.py PRODUCER_CHECKOUT EXPORT_RECEIPT --legacy-audit AUDIT_JSON --legacy-auditor AUDIT_SCRIPT`.
The command reads the producer checkout and writes only this repository's
development evidence. It does not alter loop manifests or release assets.
