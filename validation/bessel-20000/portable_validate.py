#!/usr/bin/env python3
"""Replay the unchanged accepted validators in a separate, relocatable copy.

No Mathematica, Symbolica license or producer checkout is required. Input paths
stored as historical provenance are redirected only to their byte-identical
bundled counterparts. The accepted input bundle remains immutable.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode=True

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod

def main():
    if not __debug__:raise RuntimeError('Run acceptance checks with assertions enabled')
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();base=Path(__file__).resolve().parent;out=args.output.resolve()
    if out==base or base in out.parents:raise ValueError('Output must be outside the accepted bundle')
    if out.exists():raise FileExistsError('Refusing to replace an existing replay directory')
    manifest=json.loads((base/'bundle-manifest.json').read_text())
    for name,digest in manifest['files_sha256'].items():
        if sha(base/name)!=digest:raise ValueError('Bundle checksum mismatch: '+name)
    shutil.copytree(base,out)
    oracle=load('bessel_oracle_replay',out/'validate_mathematica.py')
    argv=sys.argv;sys.argv=[str(out/'validate_mathematica.py')]
    try:oracle.main()
    finally:sys.argv=argv
    original='/shared/codex-1/vakint_rustred/workspace/precision-periods/bessel'
    receipts={
      '/shared/codex-2/vacuum_masters/MASTERS/pslq/artifacts/PR4-three-anchor-independent-MMA-replay-source-v1/root-exact-matrix-and-required-first-jet-depth-adoption-v1.json':'source-receipts/root-exact-map-adoption.json',
      '/shared/codex-2/vacuum_masters/MASTERS/pslq/artifacts/PR4-three-anchor-existing-program-inverse-exact-v2/exact-output-v1/exact-native-candidate/exact-shift-and-valuations.json':'source-receipts/exact-shift-and-valuations.json',
      '/shared/codex-2/vacuum_masters/MASTERS/pslq/artifacts/PR4-K5-first-jet-stage200-pilot-source-v1/root-actual-basis-only-stage200-adoption-v1.json':'source-receipts/root-mathematica200-adoption.json',
    }
    validator=load('bessel_acceptance_replay',out/'validate.py')
    def historical_path(value,*args):
        p=Path(value,*args);s=str(p)
        if p==out or out in p.parents:return p
        if s in receipts:return out/receipts[s]
        if s==original:return out
        if s.startswith(original+'/'):return out/s[len(original)+1:]
        return p
    validator.Path=historical_path
    validator.main()
    for name in ['constants20000.json','validation.json']:
        if sha(out/name)!=manifest['files_sha256'][name]:
            raise ValueError('Replay output differs from accepted bytes: '+name)
    print('Portable replay reproduced the accepted payload and receipt byte for byte.')

if __name__=='__main__':main()
