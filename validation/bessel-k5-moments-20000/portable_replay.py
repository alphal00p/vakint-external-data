#!/usr/bin/env python3
"""Replay the direct finite-K5 data adaptation in a new output directory."""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
if not __debug__:raise RuntimeError('Publication validation requires assertions enabled')
HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);args=ap.parse_args();out=Path(args.output).resolve()
    if out.exists():raise ValueError('Choose a new output directory to preserve earlier receipts')
    manifest=json.loads((HERE/'bundle-manifest.json').read_text())
    for name,digest in manifest['files_sha256'].items():
        path=Path(name)
        if path.is_absolute() or '..' in path.parts or sha(HERE/path)!=digest:raise ValueError('Invalid or changed primitive source bundle entry: '+name)
    out.mkdir(parents=True)
    for name in manifest['files_sha256']:
        target=out/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(HERE/name,target)
    subprocess.run([sys.executable,str(out/'export.py')],check=True,cwd=out)
    for name,digest in manifest['replay_expected_sha256'].items():
        if sha(out/name)!=digest:raise ValueError('Direct finite primitive adaptation did not reproduce '+name)
    print('PASS: finiteK5primitive payload and validation reproduced byte for byte')
if __name__=='__main__':main()
