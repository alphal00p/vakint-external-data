# Numerical migration evidence

These deterministic gzip files preserve the 464 legacy HPL projection values,
the 200- and 20,000-digit comparison results, all 324 computed complex words,
independent GiNaC checks, and shared-constant validation. They are development
reference material and are excluded from runtime loop packs.

The coefficient supplement adds the 25 previously omitted, known Laurent
coefficients. Its exporter, verification report and exact master-formula source
inputs are archived here as well; all old coefficient rows were checked before
the new rows were appended.

`manifest.json` checksums compressed and original bytes. The validator source,
dependency lockfile and original parallel coordinator are retained as execution
provenance; their original local paths must be adjusted when reproducing the run.
The Symbolica source revision is recorded explicitly. No license value or
Mathematica dependency is included.

The shared-constant report distinguishes agreement with a rounded source literal
from a strict relative-error target. Preserve those distinctions when replacing
finite tables with exact algorithms. Regenerate this archive with
`python3 tools/archive_validation.py VALIDATION_DIRECTORY --validator-source VALIDATOR_CRATE --symbolica-revision COMMIT --vakint-source VAKINT_CRATE`.
