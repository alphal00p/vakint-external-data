#!/usr/bin/env python3
"""Replay immutable high-guard source evidence in a new output directory."""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
if not __debug__:raise RuntimeError('Assertions must remain enabled')
HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);args=ap.parse_args()
    out=Path(args.output).resolve()
    if out.exists():raise ValueError('Choose a new output directory to preserve existing results')
    manifest=json.loads((HERE/'bundle-manifest.json').read_text())
    for n,h in manifest['files_sha256'].items():
        p=Path(n)
        if p.is_absolute() or '..' in p.parts:raise ValueError('Unsafe bundle path')
        if sha(HERE/p)!=h:raise ValueError('Bundle input checksum mismatch: '+n)
    out.mkdir(parents=True)
    for n in manifest['files_sha256']:
        target=out/n;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(HERE/n,target)
    subprocess.run([sys.executable,str(out/'accept.py')],check=True,cwd=out)
    for n,h in manifest['replay_expected_sha256'].items():
        if sha(out/n)!=h:raise ValueError('Independent acceptance did not reproduce '+n)
    print('PASS: high-guard acceptance, all coefficients and independent oracle checks reproduced byte for byte')
if __name__=='__main__':main()
