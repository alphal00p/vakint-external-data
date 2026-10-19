#!/usr/bin/env python3
"""Check and archive accepted producer receipts without changing runtime data."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def checked_read(path, checksum, producer):
    path = Path(path).resolve()
    if not path.is_relative_to(producer):
        raise ValueError(
            f"producer receipt points outside the requested checkout: {path}"
        )
    raw = path.read_bytes()
    if digest(raw) != checksum:
        raise ValueError(f"producer receipt hash mismatch: {path}")
    return raw


def archive(name, raw):
    if b"S-130-" in raw:
        raise ValueError(f"refusing to archive a development license: {name}")
    path = ROOT / "validation" / f"{name}.gz"
    with (
        path.open("wb") as stream,
        gzip.GzipFile(
            filename="", fileobj=stream, mode="wb", mtime=0, compresslevel=9
        ) as compressed,
    ):
        compressed.write(raw)
    return {
        "path": path.name,
        "sha256": digest(path.read_bytes()),
        "bytes": path.stat().st_size,
        "uncompressed_sha256": digest(raw),
        "uncompressed_bytes": len(raw),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("producer", type=Path)
    parser.add_argument("export_receipt", type=Path)
    parser.add_argument("--legacy-audit", type=Path, required=True)
    parser.add_argument("--legacy-auditor", type=Path, required=True)
    args = parser.parse_args()
    producer = args.producer.resolve()
    export_raw = args.export_receipt.read_bytes()
    export = json.loads(export_raw)
    by_hash = {}
    for source, checksum in export["source_sha256"].items():
        by_hash.setdefault(checksum, []).append(Path(source))
    manifest = json.loads((ROOT / "4L/manifest.json").read_text())
    summaries = []
    records = [archive("producer-export-receipt.json", export_raw)]
    for master in manifest["masters"]:
        opaque = [c for c in master["coefficients"] if not c["symbolic"]]
        if not opaque:
            continue
        checksum = master["acceptance_sha256"]["validation"]
        candidates = by_hash[checksum]
        source = next(
            (p for p in candidates if master["master_id"] in str(p)), candidates[0]
        )
        raw = checked_read(source, checksum, producer)
        validation = json.loads(raw)
        if (
            validation["master_id"] != master["master_id"]
            or validation["status"] != "accepted"
            or validation["stage_digits"] < master["significant_digits"]
        ):
            raise ValueError(
                f"acceptance identity or precision mismatch: {master['name']}"
            )
        computed = validation["files"]["computed.json"]
        payload = checked_read(computed["path"], computed["sha256"], producer)
        local = ROOT / "4L" / master["files"]["numerical.json"]["path"]
        if payload != local.read_bytes():
            raise ValueError(
                f"exported coefficients differ from accepted producer: {local}"
            )
        record = archive(f"producer-4L-{master['name']}-validation.json", raw)
        records.append(record)
        numerical = validation.get("numerical", {})
        summaries.append(
            {
                "master_id": master["master_id"],
                "name": master["name"],
                "opaque_coefficients": len(opaque),
                "accepted_digits": validation["stage_digits"],
                "validation": record["path"],
                "validation_sha256": checksum,
                "computed_sha256": computed["sha256"],
                "exported_payload_byte_identical": True,
                "numerical_flags": {
                    key: value
                    for key, value in numerical.items()
                    if isinstance(value, (int, bool))
                },
                "coefficient_checks": [
                    {
                        key: value
                        for key, value in coefficient.items()
                        if key
                        in (
                            "power",
                            "passed",
                            "exact_zero",
                            "compared_significant_digits",
                            "independently_rounded_strings_identical",
                        )
                    }
                    for coefficient in numerical.get("coefficients", [])
                ],
            }
        )
    summary = {
        "schema": "vakint.external-data.producer-provenance.v1",
        "data_version": manifest["version"],
        "loop_manifest_sha256": digest((ROOT / "4L/manifest.json").read_bytes()),
        "source_export_receipt_sha256": digest(export_raw),
        "source_coverage_sha256": export["source_coverage_sha256"],
        "masters": summaries,
        "master_count": len(summaries),
        "opaque_coefficient_count": sum(m["opaque_coefficients"] for m in summaries),
    }
    records.append(
        archive(
            "producer-provenance-summary.json",
            (json.dumps(summary, indent=2) + "\n").encode(),
        )
    )
    records.append(
        archive("opaque-four-loop-audit.json", args.legacy_audit.read_bytes())
    )
    records.append(
        archive("audit_opaque_four_loop.py", args.legacy_auditor.read_bytes())
    )
    evidence_path = ROOT / "validation/manifest.json"
    evidence = json.loads(evidence_path.read_text())
    existing = {entry["path"]: entry for entry in evidence["files"]}
    existing.update({entry["path"]: entry for entry in records})
    evidence["files"] = [existing[name] for name in sorted(existing)]
    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n")
    print(
        f"Verified and archived {len(summaries)} accepted master receipts "
        f"binding {summary['opaque_coefficient_count']} numerical-only coefficients"
    )


if __name__ == "__main__":
    main()
