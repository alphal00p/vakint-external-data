#!/usr/bin/env python3
"""Verify immutable bundled inputs, then run the reviewer in a fresh directory."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

bundle = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
output = args.output.resolve()
if output.exists() or output == bundle or bundle in output.parents:
    raise ValueError('Replay requires a new directory outside the sealed bundle')
manifest = json.loads((bundle / 'bundle-manifest.json').read_bytes())
for relative, expected in manifest['file_sha256'].items():
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Unsafe manifest path')
    actual = hashlib.sha256((bundle / path).read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(f'Bundle hash mismatch: {relative}')
output.mkdir(parents=True)
shutil.copytree(bundle / 'inputs', output / 'inputs')
for path in (bundle / 'reviewer').iterdir():
    shutil.copyfile(path, output / path.name)
subprocess.run([sys.executable, str(output / 'audit.py')], check=True, cwd=output)
subprocess.run([sys.executable, str(output / 'audit_payload.py')], check=True, cwd=output)
formula = json.loads((output / 'audit.json').read_bytes())
payload = json.loads((output / 'moment-payload-audit.json').read_bytes())
original = json.loads((bundle / 'original/audit.json').read_bytes())
for key in ['accepted', 'upstream_commit', 'mapping', 'normalization', 'proof', 'exact_formula_checks', 'numerical_checks', 'limits']:
    if formula[key] != original[key]:
        raise ValueError(f'Portable scientific verdict differs: {key}')
if not payload['accepted'] or len(payload['checks']) != 8:
    raise ValueError('Portable finite-payload verdict differs')
receipt = {
    'accepted': True, 'scientific_formula_verdict_identical': True,
    'exact_formula_checks': len(formula['exact_formula_checks']),
    'numerical_formula_checks': len(formula['numerical_checks']),
    'finite_payload_checks': len(payload['checks']),
    'original_formula_receipt_sha256': hashlib.sha256((bundle / 'original/audit.json').read_bytes()).hexdigest(),
    'bundle_manifest_sha256': hashlib.sha256((bundle / 'bundle-manifest.json').read_bytes()).hexdigest(),
    'no_git_network_producer_or_mathematica_access': True,
}
(output / 'portable-replay.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt))
