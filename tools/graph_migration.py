#!/usr/bin/env python3
"""Preserve native graph/model migration provenance and producer bindings."""

from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path

import data

SCHEMA = "vakint.external-data.graph-migration.v1"
RECEIPT = "provenance/native-graphs/migration.json"


def sha256_text(value):
    return hashlib.sha256(value.encode()).hexdigest()


def accepts_producer_binding(expected, master, root=data.ROOT):
    """An original producer graph binding remains valid only through this receipt."""
    directory = Path(root) / f"{master['loop_count']}L"
    from model_identity import accepts_graph, context

    identity = context(root)
    actual = master["files"]["graph.dot"]
    relative = f"{master['loop_count']}L/{actual['path']}"
    if expected["path"] == actual["path"] and accepts_graph(
        root, relative, expected["sha256"], actual["sha256"], identity
    ):
        return True
    receipt_path = directory / "graph-migration.json"
    if not receipt_path.exists():
        return False
    receipt = data.read_json(receipt_path)
    if receipt["schema"] != SCHEMA:
        raise ValueError("unsupported native graph migration receipt")
    for record in receipt["graphs"]:
        if record["path"] != actual["path"]:
            continue
        original = record["original_dot"]
        if sha256_text(original) != record["original_sha256"]:
            raise ValueError("original graph migration provenance is corrupt")
        return (
            expected["path"] == actual["path"]
            and expected["sha256"] == record["original_sha256"]
            and (actual["sha256"] == record["canonical_sha256"] or accepts_graph(
                root, relative, record["canonical_sha256"], actual["sha256"], identity
            ))
            and data.digest(data.checked_path(directory, actual["path"]))
            == actual["sha256"]
        )
    return False


def migrate(native_artifacts, root=data.ROOT):
    """Install checked output of FeynKit's native serializer, retaining all inputs.

    The native producer must verify complete saved routing, half-edge order,
    numerators and graph powers before writing the artifacts. Its model output
    is Model::to_json_pretty and graph output is FeynmanDiagram::to_dot.
    """
    root, native_artifacts = Path(root), Path(native_artifacts)
    if (root / RECEIPT).exists():
        raise ValueError("native graph migration already exists; validate it instead")
    original = data.read_json(root / "provenance/original-root/manifest.json")
    models, graphs = [], []
    for loops in range(1, 6):
        model_path = f"{loops}L/model.json"
        archived = f"provenance/native-graphs/original/{model_path}"
        data.copy_verified(root / model_path, root / archived)
        canonical = native_artifacts / model_path
        fingerprint = (canonical.parent / "fingerprint.txt").read_text().strip()
        models.append(
            {
                "path": model_path,
                "original": archived,
                "original_sha256": data.digest(root / archived),
                "canonical_sha256": data.digest(canonical),
                "model_fingerprint": fingerprint,
                "source": "derived from 4L/model.json"
                if loops == 5
                else "migrated payload",
            }
        )
        shutil.copyfile(canonical, root / model_path)
        if loops == 5:
            continue
        loop_graphs = []
        masters = [m for m in original["masters"] if m["loop_count"] == loops]
        sources = {
            f"{master['directory']}/graph.dot": native_artifacts
            / master["directory"]
            / "graph.dot"
            for master in masters
        }
        for family in original["families"]:
            if len(family["loop_momenta"]) != loops:
                continue
            maximal = max(
                (m for m in masters if m["family_sha256"] == family["sha256"]),
                key=lambda m: (
                    sum(p > 0 for p in m["powers"]),
                    -sum(max(p, 0) for p in m["powers"]),
                ),
            )
            sources[f"{loops}L/graphs/{family['sha256']}.dot"] = (
                native_artifacts / maximal["directory"] / "graph.dot"
            )
        for path, canonical in sorted(sources.items()):
            archived = f"provenance/native-graphs/original/{path}"
            data.copy_verified(root / path, root / archived)
            record = {
                "path": path,
                "original": archived,
                "original_sha256": data.digest(root / archived),
                "canonical_sha256": data.digest(canonical),
            }
            graphs.append(record)
            loop_graphs.append(
                {
                    **record,
                    "path": str(Path(path).relative_to(f"{loops}L")),
                    "original_dot": (root / archived).read_text(),
                }
            )
            shutil.copyfile(canonical, root / path)
        data.write_json(
            root / f"{loops}L/graph-migration.json",
            {"schema": SCHEMA, "graphs": loop_graphs},
        )
    data.write_json(
        root / RECEIPT,
        {
            "schema": SCHEMA,
            "native_model_codec": "feynkit_model::Model JSON",
            "native_graph_codec": "feynkit_graph::FeynmanDiagram saved DOT",
            "preserved_semantics": [
                "model-resolved scalar particles and interactions",
                "complete spanning-forest loop routing and independent-edge order",
                "half-edge order and model vertex slots",
                "master numerator and positive propagator powers",
            ],
            "models": models,
            "graphs": graphs,
        },
    )
    validate(root)


def validate(root=data.ROOT):
    root = Path(root)
    from model_identity import accepts_graph, validate as validate_identity

    identity = validate_identity(root)
    receipt = data.read_json(root / RECEIPT)
    if receipt["schema"] != SCHEMA:
        raise ValueError("unsupported native graph migration receipt")
    for record in receipt["models"] + receipt["graphs"]:
        if (
            (data.digest(data.checked_path(root, record["path"]))
            != record["canonical_sha256"] and not accepts_graph(
                root, record["path"], record["canonical_sha256"],
                data.digest(data.checked_path(root, record["path"])), identity
            ))
            or data.digest(data.checked_path(root, record["original"]))
            != record["original_sha256"]
        ):
            raise ValueError(f"native migration checksum mismatch: {record['path']}")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-artifacts", type=Path)
    arguments = parser.parse_args()
    if arguments.native_artifacts:
        migrate(arguments.native_artifacts)
    else:
        validate()
    print("Validated native graph/model migration provenance")
