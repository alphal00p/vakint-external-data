"""Replay the audited native model/graph notation migration without a CAS.

This adapter never accepts a legacy fingerprint at runtime. It installs the new
native fingerprint and exact producer-verified numerator expressions, preserving
the original DOTs and all unrelated bytes. Numerical and IBP data are untouched.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path

import data

BASE = Path("provenance/native-graph-identity-v2")
RECEIPT = BASE / "migration.json"
SCHEMA = "vakint.external-data.native-graph-identity.v1"
PROOF_SHA256 = "ad731ba1ea49f90aaae06510a8b0c642510b68353fcbee99f3575ad777128176"
ALIAS_SHA256 = "dbdce1a6abbef4ba43610d4eba40f543db02c66c6e12953d661eb48c199683c6"
RENAMING = {
    "FeynKit::Momentum": "gammalooprs::Q",
    "FeynKit::LoopMomentum": "gammalooprs::K",
    "FeynKit::ExternalMomentum": "gammalooprs::P",
}
ATTRIBUTES = re.compile(
    r'\b(numerator|numerator_prefactor|projector)=("(?:[^"\\]|\\.)*")'
)
FINGERPRINT = re.compile(r'\bmodel_fingerprint="([0-9a-f]{64})"')


def text_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def reference(root, path):
    return {"path": str(path), **data.file_record(data.checked_path(root, str(path)))}


def checked(root, ref):
    path = data.checked_path(root, ref["path"])
    if data.file_record(path) != {key: ref[key] for key in ("sha256", "bytes")}:
        raise ValueError(f"graph identity provenance changed: {ref['path']}")
    return path


def transform_dot(original, old_fingerprint, new_fingerprint, expressions):
    """Edit only JSON-quoted fields of the authenticated saved DOT dialect."""
    matches = list(FINGERPRINT.finditer(original))
    if len(matches) != 1 or matches[0].group(1) != old_fingerprint:
        raise ValueError("graph does not carry exactly the expected old model identity")
    migrated = FINGERPRINT.sub(f'model_fingerprint="{new_fingerprint}"', original)

    def expression(match):
        value = json.loads(match.group(2))
        if value in expressions:
            return (
                match.group(1)
                + "="
                + json.dumps(expressions[value], ensure_ascii=False)
            )
        if any(old in value for old in RENAMING):
            raise ValueError("graph numerator lacks an exact native expression mapping")
        return match.group(0)

    migrated = ATTRIBUTES.sub(expression, migrated)
    if any(old in migrated for old in RENAMING):
        raise ValueError(
            "legacy momentum notation outside the admitted expression fields"
        )
    return migrated


def proof_context(root, receipt):
    evidence = checked(root, receipt["proof"])
    if data.digest(evidence) != PROOF_SHA256:
        raise ValueError("unknown native graph identity proof")
    proof = data.read_json(evidence)
    if proof["status"] != "passed" or proof["scope"]["external_master_graphs"] != 755:
        raise ValueError("native graph migration proof is incomplete")
    files = {}
    for item in proof["evidence"]:
        name = Path(item["path"]).name
        # Build executables are identified by the immutable proof, not shipped.
        if name == "b3":
            continue
        path = evidence.parent / name
        if data.file_record(path) != {key: item[key] for key in ("sha256", "bytes")}:
            raise ValueError(f"native graph evidence differs: {name}")
        files[name] = path
    mapping = data.read_json(files["native-expression-mapping.json"])
    if mapping["renaming"] != RENAMING or mapping["allowed_dot_attributes"] != [
        "numerator",
        "numerator_prefactor",
        "projector",
    ]:
        raise ValueError("graph migration attempts a different symbol or field rewrite")
    expressions = {}
    for row in mapping["expressions"]:
        old, new = row["old_expression"], row["new_expression"]
        if (
            row["inverse_rename_exact"] is not True
            or old in expressions
            or text_hash(old) != row["original_sha256"]
            or text_hash(new) != row["migrated_sha256"]
            or row["source_atom_bytes"] != row["migrated_atom_bytes"]
        ):
            raise ValueError(
                "native graph expression mapping is not an exact invertible projection"
            )
        expressions[old] = new
    if len(expressions) != 147:
        raise ValueError("native expression mapping inventory differs")
    comparison = data.read_json(files["preimage-comparison.json"])
    models = {}
    for label, old_name, new_name in [
        ("external-1L", "vendored-1L-old.json", "vendored-1L-new.json"),
        ("external-2L", "external-2L-old.json", "external-2L-new.json"),
    ]:
        identity = next(item for item in comparison if item["label"] == label)
        old = data.read_json(files[old_name])
        expected = copy.deepcopy(old)
        particle = expected["particles"][0]
        if (
            particle["spin"] != 1
            or particle["charge"] != 0
            or particle["y_charge"] != 0
        ):
            raise ValueError(
                "model identity transition is not the audited neutral scalar"
            )
        particle.update(charge="0", y_charge="0", y_charge_right=None)
        expected["propagators"][0]["denominator"] = "(P(idx(1,1)))^2+-1*mUV^2"
        expected["couplings"][0]["expression"] = "(-𝑖)*g"
        expected["couplings"][1]["expression"] = "(-𝑖)*lam"
        if expected != data.read_json(files[new_name]):
            raise ValueError(
                "model preimages differ beyond the six audited representation fields"
            )
        models[identity["source_sha256"]] = {**identity, "source_definition": old}
    native = data.read_json(files["semantic-migration-validation.json"])
    graphs = {}
    for report in native["reports"]:
        if report["label"].startswith("external-"):
            loop = report["label"].removeprefix("external-")
            for graph in report["graphs"]:
                graphs[f"{loop}/{graph['path']}"] = graph
    if len(graphs) != 755:
        raise ValueError("native public master graph validation is incomplete")
    aliases = evidence.parent / "native-graph-alias-proof.json"
    if data.digest(aliases) != ALIAS_SHA256:
        raise ValueError("native family graph alias proof changed")
    alias_proof = data.read_json(aliases)
    if alias_proof["sealed_master_proof_sha256"] != PROOF_SHA256:
        raise ValueError("native graph alias proof references another master proof")
    for alias in alias_proof["aliases"]:
        if alias["scope"] == "external":
            prefix = f"{alias['loop_count']}L/"
            native = graphs[prefix + alias["identical_validated_master_path"]]
            if native["source_sha256"] != alias["sha256"]:
                raise ValueError("native family graph alias differs from its master")
            graphs[prefix + alias["path"]] = native
    if len(graphs) != 763:
        raise ValueError("native graph alias inventory differs")
    return {"expressions": expressions, "models": models, "native_graphs": graphs}


def context(root):
    path = Path(root) / RECEIPT
    if not path.exists():
        return None
    receipt = data.read_json(path)
    if receipt["schema"] != SCHEMA:
        raise ValueError("unknown native graph identity migration")
    return {"receipt": receipt, **proof_context(root, receipt)}


def accepts_graph(root, path, previous_sha256, current_sha256, ctx=None):
    ctx = context(root) if ctx is None else ctx
    if ctx is None:
        return False
    row = ctx["receipt"]["graphs"].get(str(path))
    native = ctx["native_graphs"].get(str(path))
    if (
        row is None
        or native is None
        or row["original"]["sha256"] != native["source_sha256"]
        or row["current_sha256"] != native["migrated_sha256"]
        or row["original"]["sha256"] != previous_sha256
        or row["current_sha256"] != current_sha256
    ):
        return False
    original = checked(root, row["original"]).read_text()
    actual = data.checked_path(root, str(path)).read_text()
    model = ctx["models"][row["model_source_sha256"]]
    return text_hash(actual) == current_sha256 and actual == transform_dot(
        original, model["old_blake3"], model["new_blake3"], ctx["expressions"]
    )


def validate(root):
    ctx = context(root)
    if ctx is None:
        return None
    if set(ctx["receipt"]["graphs"]) != set(ctx["native_graphs"]) or set(
        ctx["receipt"]["unchanged_models"]
    ) != {f"{loops}L/model.json" for loops in range(1, 6)}:
        raise ValueError("native graph identity migration inventory is incomplete")
    for path, row in ctx["receipt"]["graphs"].items():
        if not accepts_graph(
            root, path, row["original"]["sha256"], row["current_sha256"], ctx
        ):
            raise ValueError(f"native graph identity projection changed: {path}")
    for path, ref in ctx["receipt"]["unchanged_models"].items():
        model = data.checked_path(root, path)
        if data.file_record(model) != ref:
            raise ValueError("model JSON changed during graph identity migration")
        identity = ctx["models"][ref["sha256"]]
        if data.read_json(model) != identity["source_definition"]:
            raise ValueError("model source differs from its audited canonical preimage")
    return ctx


def migrate(root, evidence):
    root, evidence = Path(root).resolve(), Path(evidence).resolve()
    if (root / RECEIPT).exists():
        raise ValueError("native graph identity migration already installed")
    proof = data.read_json(evidence / "sealed-migration-proof.json")
    if data.digest(evidence / "sealed-migration-proof.json") != PROOF_SHA256:
        raise ValueError("unknown native graph migration proof")
    destination = root / BASE / "evidence"
    destination.mkdir(parents=True)
    data.copy_verified(
        evidence / "sealed-migration-proof.json",
        destination / "sealed-migration-proof.json",
    )
    data.copy_verified(
        evidence / "native-graph-alias-proof.json",
        destination / "native-graph-alias-proof.json",
    )
    for item in proof["evidence"]:
        name = Path(item["path"]).name
        if name != "b3":
            data.copy_verified(evidence / name, destination / name)
    receipt = {
        "schema": SCHEMA,
        "source_revision": proof["producers"]["external_source_revision"],
        "proof": reference(root, BASE / "evidence/sealed-migration-proof.json"),
        "graphs": {},
        "unchanged_models": {},
        "development_executables": "host/helper hashes remain in the original proof; no executable is required by source validation",
    }
    ctx = proof_context(root, receipt)
    release = data.read_json(root / "manifest.json")
    updates = []
    for pack in release["loop_packs"]:
        directory = root / f"{pack['loop_count']}L"
        manifest_path = data.checked_path(root, pack["manifest"])
        if data.digest(manifest_path) != pack["manifest_sha256"]:
            raise ValueError("source loop manifest hash differs")
        manifest = data.read_json(manifest_path)
        source_model = data.file_record(directory / "model.json")
        model = ctx["models"][source_model["sha256"]]
        if data.read_json(directory / "model.json") != model["source_definition"]:
            raise ValueError("source scalar model differs from its native preimage")
        receipt["unchanged_models"][f"{pack['loop_count']}L/model.json"] = source_model
        for name, record in manifest["files"].items():
            if not name.endswith(".dot"):
                continue
            path = data.checked_path(directory, name)
            if data.file_record(path) != record:
                raise ValueError(
                    "source DOT hash differs from its authenticated inventory"
                )
            original = path.read_text()
            if not FINGERPRINT.search(original):
                continue
            relative = path.relative_to(root).as_posix()
            migrated = transform_dot(
                original, model["old_blake3"], model["new_blake3"], ctx["expressions"]
            )
            native = ctx["native_graphs"].get(relative)
            if (
                native is None
                or native["source_sha256"] != record["sha256"]
                or native["migrated_sha256"] != text_hash(migrated)
            ):
                raise ValueError(
                    "DOT projection differs from actual native semantic validation"
                )
            archived = BASE / "original" / relative
            data.copy_verified(path, root / archived)
            receipt["graphs"][relative] = {
                "original": reference(root, archived),
                "current_sha256": text_hash(migrated),
                "model_source_sha256": source_model["sha256"],
            }
            updates.append((path, migrated.encode()))
            record.update(sha256=text_hash(migrated), bytes=len(migrated.encode()))
        for master in manifest["masters"]:
            graph = master["files"]["graph.dot"]
            graph["sha256"] = manifest["files"][graph["path"]]["sha256"]
        updates.append(
            (
                manifest_path,
                (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode(),
            )
        )
        pack["manifest_sha256"] = hashlib.sha256(updates[-1][1]).hexdigest()
    # All native mappings and hashes have been checked before changing runtime files.
    for path, payload in updates:
        path.write_bytes(payload)
    data.write_json(root / "manifest.json", release)
    data.write_json(root / RECEIPT, receipt)
    validate(root)
    return {
        "graphs": len(receipt["graphs"]),
        "masters_with_native_proof": 755,
        "models_unchanged": len(receipt["unchanged_models"]),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=data.ROOT)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    result = migrate(args.root, args.evidence) if args.evidence else validate(args.root)
    print(
        json.dumps({"validated": result is not None} if not args.evidence else result)
    )
