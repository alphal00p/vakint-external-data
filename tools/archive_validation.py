#!/usr/bin/env python3
"""Preserve the numerical migration evidence outside downloadable runtime packs."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

FILES = (
    "hpl-legacy-reference.json",
    "hpl-parity-200.json",
    "hpl-values-200.tsv",
    "hpl-parity-20000.json",
    "hpl-values-20000.tsv",
    "hpl-ginac-reference.json",
    "run_hpl_20k.py",
    "shared-constant-references.json",
    "shared-constant-validation.json",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--validator-source", type=Path, required=True)
    parser.add_argument("--symbolica-revision", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / "validation"
    root.mkdir(exist_ok=True)
    source_files = [(name, args.source / name) for name in FILES]
    source_files += [
        ("validator-main.rs", args.validator_source / "src/main.rs"),
        ("validator-Cargo.toml", args.validator_source / "Cargo.toml"),
        ("validator-Cargo.lock", args.validator_source / "Cargo.lock"),
    ]
    records = []
    for name, source in source_files:
        raw = source.read_bytes()
        if b"S-130-" in raw:
            raise ValueError(
                f"refusing to archive an embedded development license: {name}"
            )
        path = root / f"{name}.gz"
        with (
            path.open("wb") as stream,
            gzip.GzipFile(
                filename="", fileobj=stream, mode="wb", mtime=0, compresslevel=9
            ) as compressed,
        ):
            compressed.write(raw)
        records.append(
            {
                "path": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
                "uncompressed_sha256": hashlib.sha256(raw).hexdigest(),
                "uncompressed_bytes": len(raw),
            }
        )
    report = json.loads((args.source / "hpl-parity-20000.json").read_text())
    if (
        not report["passed"]
        or report["projection_count"] != 464
        or report["digits"] != 20000
    ):
        raise ValueError("the complete 464-projection 20,000-digit gate must pass")
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "schema": "vakint.external-data.validation-evidence.v1",
                "symbolica_revision": args.symbolica_revision,
                "hpl_convention": "Standard HPL at exp(i*pi/3); HR and HI are plain real and imaginary parts",
                "files": records,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"Archived {len(records)} checksummed numerical validation sources/results")


if __name__ == "__main__":
    main()
