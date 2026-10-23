#!/usr/bin/env python3
"""Stage and install a current native five-loop publication without rebuilding 1–4L.

The terminal definitions must come from the native application exporter. This
tool writes graph descriptions and metadata; it never derives reduction rules,
terminal relations, numerical coefficients or cache entries.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

import data
import five_loop_graphs

CURRENT = "provenance/current-publication.json"
SCHEMA = "vakint.external-data.current-five-loop.v1"


def inventory(directory):
    directory = Path(directory)
    entries = list(directory.rglob("*"))
    if any(path.is_symlink() for path in entries):
        raise ValueError(f"symlink in source inventory: {directory}")
    return {
        path.relative_to(directory).as_posix(): data.file_record(path)
        for path in sorted(entries)
        if path.is_file()
    }


def lower_snapshot(root):
    root = Path(root)
    release = data.read_json(root / "manifest.json")
    return {
        "loop_entries": [p for p in release["loop_packs"] if p["loop_count"] < 5],
        "files": {f"{n}L/{k}": v for n in range(1, 5)
                  for k, v in inventory(root / f"{n}L").items()},
    }


def terminal_records(definitions, expected=None):
    """Use native identities, with reproducible display names independent of history."""
    families = {}
    for family in definitions["families"]:
        fingerprint = family["fingerprint"]
        digest = hashlib.sha256(fingerprint.encode()).hexdigest()
        if family.get("sha256", digest) != digest:
            raise ValueError("native family fingerprint and SHA256 disagree")
        if fingerprint in families or len(family["loop_momenta"]) != 5:
            raise ValueError("duplicate or non-five-loop family")
        families[fingerprint] = {**family, "sha256": digest}
    keys = []
    for master in definitions["masters"]:
        fingerprint = master["family_fingerprint"]
        if fingerprint not in families:
            raise ValueError("terminal references an undeclared native family")
        powers = master["powers"]
        if (not isinstance(powers, list)
                or any(type(power) is not int for power in powers)
                or len(powers) != len(families[fingerprint]["denominators"])):
            raise ValueError("invalid signed terminal index tuple")
        keys.append((fingerprint, tuple(powers)))
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate native terminal key")
    if not keys or (expected is not None and len(keys) != expected):
        raise ValueError("native terminal count differs from the requested publication")
    records = []
    for index, (fingerprint, powers) in enumerate(sorted(keys), 1):
        family = families[fingerprint]
        suffix = "_".join(f"{'m' if n < 0 else 'p'}{abs(n)}" for n in powers)
        records.append({
            "master_id": f"L5_{family['sha256']}_{suffix}",
            "family_sha256": family["sha256"], "loop_count": 5,
            "powers": list(powers), "name": f"P{index}",
            "directory": f"masters/P{index}", "status": "not_computed",
            "kind": "uncomputed-terminal", "exact_basis_expression": None,
            "available_epsilon_powers": [], "symbolic_powers": [],
            "coefficients": [],
        })
    return list(families.values()), records


def validate_family(family, momenta):
    """Authenticate the existing census against the native massive denominator basis."""
    from fractions import Fraction

    if family.get("external_momenta") or len(family["denominators"]) != len(momenta):
        raise ValueError("native family is incompatible with the vacuum census")
    if any(Fraction(value) for value in family.get("power_shifts", [])):
        raise ValueError("the vacuum census requires integer propagator powers")
    for definition, momentum in zip(family["denominators"], momenta):
        expected = []
        for coordinate in family["coordinates"]:
            if coordinate["kind"] != "loop_loop":
                raise ValueError("non-vacuum scalar-product coordinate")
            left, right = coordinate["left"], coordinate["right"]
            expected.append(momentum[left] * momentum[right] * (1 if left == right else 2))
        if (list(map(Fraction, definition["coefficients"])) != expected
                or Fraction(definition["constant"]) != -1):
            raise ValueError("native family denominators differ from the graph census")


def stage(root, application, definitions_path, output, expected=None,
          rustred_revision=None, vakint_revision=None, consumer_rustred_revision=None):
    root, application, output = map(lambda p: Path(p).resolve(), (root, application, output))
    if output.exists():
        raise ValueError("staging destination already exists; choose a new destination")
    if output.is_relative_to(root / "5L"):
        raise ValueError("staging must not modify the active five-loop pack")
    before = lower_snapshot(root)
    definitions = data.read_json(definitions_path)
    families, records = terminal_records(definitions, expected)
    native = data.read_json(application / "application.json")
    metadata = native["metadata"]
    if native["schema"] != "rustred.saved-application.v1":
        raise ValueError("unsupported native application schema")
    if metadata["remaining_terminals"] != len(records):
        raise ValueError("native application and terminal inventory counts differ")
    for field in ("source_manifest_blake3", "source_scope_binding"):
        value = definitions.get(field, definitions.get("metadata", {}).get(field))
        if value is None or value != metadata.get(field):
            raise ValueError(f"native terminal inventory has a different {field}")
    previous_root = data.ROOT
    try:
        data.ROOT = root
        momenta, parents, witnesses = data.five_loop_definitions()
    finally:
        data.ROOT = previous_root
    for family in families:
        validate_family(family, momenta)
    source_files = inventory(application)
    output.mkdir(parents=True)
    shutil.copytree(application, output / "ibps")
    if inventory(output / "ibps") != source_files:
        raise ValueError("native application changed during copying")
    shutil.copyfile(root / "4L/model.json", output / "model.json")
    model_source = (root / "4L/masters/P1/graph.dot").read_text()
    fingerprint = re.search(r'model_fingerprint="([0-9a-f]{64})"', model_source)[1]
    graphs = output / "graphs"
    graphs.mkdir()
    for parent in parents:
        (graphs / f"parent-{parent['sector']}.dot").write_text(data.parent_graph(parent))
    for record in records:
        witness = five_loop_graphs.select_witness(record, witnesses)
        record["parent_graph"] = f"graphs/parent-{parents[witness['parent']]['sector']}.dot"
        graph = output / record["directory"] / "graph.dot"
        graph.parent.mkdir(parents=True)
        graph.write_text(five_loop_graphs.canonical_graph(
            record, momenta, parents, witnesses, fingerprint, display_name=record["name"]))
        record["files"] = {"graph.dot": {
            "path": graph.relative_to(output).as_posix(), "sha256": data.digest(graph)}}
    for family in families:
        family["coordinate_index_base"] = 0
        family["denominator_convention"] = "Minkowski q^2-mUV^2; stored unit mass squared"
        family["graph"] = f"graphs/{family['sha256']}.dot"
        representatives = [r for r in records if r["family_sha256"] == family["sha256"]]
        representative = max(representatives, key=lambda r: (sum(p > 0 for p in r["powers"]), r["powers"]))
        shutil.copyfile(output / representative["files"]["graph.dot"]["path"],
                        output / family["graph"])
    data.write_json(output / "terminal-definitions.json", definitions)
    data.write_json(output / "coverage.json", {
        "schema": "vakint.external-data.coverage.v1", "loop_count": 5,
        "complete_family_claim": False, "known_master_basis_complete": False,
        "cache_completion_is_coverage_certificate": False, "kind": "saved-scope",
        "authority": metadata["authority"], "metadata": metadata,
        "queries": "ibps/queries.json", "selection": "ibps/selection.json",
        "application": "ibps/application.json",
        "note": "Recorded starting predicates are authoritative; rank/D maxima alone are not blanket coverage. The terminal basis can be nonminimal and has no numerical evaluations.",
    })
    receipt = {
        "schema": SCHEMA, "application": "ibps/application.json",
        "terminal_definitions": "terminal-definitions.json",
        "source_manifest_blake3": metadata["source_manifest_blake3"],
        "source_scope_binding": metadata["source_scope_binding"],
        "source_generation": metadata["source_generation"],
        "terminal_count": len(records),
        "naming": "P1..Pn in lexicographic full-family-fingerprint/signed-index order; native identities remain family-qualified",
        "rustred_revision": rustred_revision, "vakint_revision": vakint_revision,
        "consumer_rustred_revision": consumer_rustred_revision,
        "application_sha256": data.digest(application / "application.json"),
        "terminal_definitions_sha256": data.digest(output / "terminal-definitions.json"),
        "graph_model_fingerprint": fingerprint, "numerical_work_performed": False,
        "cache_available": False, "minimality_claim": False,
    }
    data.write_json(output / CURRENT, receipt)
    data.write_json(output / "package.json", {
        **receipt, "bytes": sum(item["bytes"] for item in source_files.values()),
        "files": len(source_files),
        "files_sha256": {name: item["sha256"] for name, item in source_files.items()},
    })
    (output / "cache").mkdir()
    (output / "cache/README.md").write_text(
        "# Five-loop cache\n\nNo prepared cache is included. Generate a cache only against this immutable\napplication identity; caches for previous publications are incompatible.\n")
    (output / "README.md").write_text(
        f"# Five-loop symbolic reduction\n\nThis pack contains {len(records)} unevaluated terminal integrals and the native\nRustRed application for the recorded campaign scope. Each `masters/P*/graph.dot`\ncontains its complete numerator, masses, powers and explicit loop basis.\nThe scalar model is `model.json`. No numerical coefficients or cache are included.\n\nThe exact signed-index identity is recorded in `manifest.json`; P-numbers are\ndisplay names for this publication only. See `coverage.json` for admitted scope.\n")
    manifest = {
        "schema": data.LOOP_SCHEMA, "version": data.read_json(root / "manifest.json")["version"],
        "loop_count": 5, "dimension": "4-2*epsilon", "normalization": "FMFTandMATAD",
        "unit_mass_squared": True, "families": families, "masters": records,
        "ibps": {"kind": "saved-application", "path": "ibps", "files": [f"ibps/{name}" for name in source_files]},
        "cache": {"available": False}, "coverage": "coverage.json",
        "provenance": {"current_publication": CURRENT,
                       "master_producer_rustred_revision": rustred_revision,
                       "vakint_reference_revision": vakint_revision,
                       "native_cache_rustred_revision": None},
        "files": inventory(output),
    }
    data.write_json(output / "manifest.json", manifest)
    validate_stage(output)
    if lower_snapshot(root) != before:
        raise ValueError("lower-loop packs changed during staging")
    return {"masters": len(records), "files": len(manifest["files"]),
            "manifest_sha256": data.digest(output / "manifest.json"), "directory": str(output)}


def validate_stage(directory):
    directory = Path(directory)
    manifest = data.read_json(directory / "manifest.json")
    actual = inventory(directory)
    actual.pop("manifest.json")
    if actual != manifest["files"]:
        raise ValueError("staged inventory differs from its manifest")
    if manifest["cache"] != {"available": False}:
        raise ValueError("replacement pack must have an empty cache")
    receipt = data.read_json(directory / CURRENT)
    definitions = data.read_json(directory / receipt["terminal_definitions"])
    if (data.digest(directory / receipt["terminal_definitions"])
            != receipt["terminal_definitions_sha256"]
            or data.digest(directory / receipt["application"])
            != receipt["application_sha256"]):
        raise ValueError("publication receipt differs from its native inputs")
    _, expected = terminal_records(definitions, receipt["terminal_count"])
    if [(r["master_id"], r["name"], r["powers"]) for r in manifest["masters"]] != [
            (r["master_id"], r["name"], r["powers"]) for r in expected]:
        raise ValueError("staged terminal keys or names differ from native definitions")
    for master in manifest["masters"]:
        if master["coefficients"] or master["available_epsilon_powers"] or set(master["files"]) != {"graph.dot"}:
            raise ValueError("replacement master must have only a graph and no evaluated coefficients")
        graph = master["files"]["graph.dot"]
        if data.digest(data.checked_path(directory, graph["path"])) != graph["sha256"]:
            raise ValueError("master graph binding differs from its native graph")
        data.checked_path(directory, master["parent_graph"]).read_bytes()
    return manifest


def install(root, staged, backup):
    root, staged, backup = map(lambda p: Path(p).resolve(), (root, staged, backup))
    manifest = validate_stage(staged)
    before = lower_snapshot(root)
    release = data.read_json(root / "manifest.json")
    if manifest["version"] != release["version"]:
        raise ValueError("staged version differs from the active repository")
    if backup.exists() or backup.is_relative_to(root):
        raise ValueError("backup must be a new directory outside the data repository")
    if staged.is_relative_to(root / "5L"):
        raise ValueError("staged pack must be separate from the active pack")
    backup.mkdir(parents=True)
    for relative in ("manifest.json", "provenance/migration.json", "provenance/native-graphs/migration.json"):
        source = root / relative
        if source.exists():
            destination = backup / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
    shutil.move(str(root / "5L"), str(backup / "5L"))
    shutil.copytree(staged, root / "5L")
    migration_path = root / "provenance/migration.json"
    if migration_path.exists():
        migration = data.read_json(migration_path)
        migration["files"] = [item for item in migration["files"]
                              if not item["source"].startswith("5L/")]
        data.write_json(migration_path, migration)
    native_path = root / "provenance/native-graphs/migration.json"
    if native_path.exists():
        native = data.read_json(native_path)
        for field in ("models", "graphs"):
            native[field] = [item for item in native[field] if not item["path"].startswith("5L/")]
        data.write_json(native_path, native)
    for relative in ("provenance/five-loop-graphs", "provenance/native-graphs/original/5L"):
        path = root / relative
        if path.exists():
            target = backup / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(target))
    pack = next(p for p in release["loop_packs"] if p["loop_count"] == 5)
    pack["manifest_sha256"] = data.digest(root / "5L/manifest.json")
    pack["archive_sha256"] = pack["archive_bytes"] = None
    data.write_json(root / "manifest.json", release)
    if lower_snapshot(root) != before:
        raise ValueError("lower-loop packs or root entries changed during installation")
    return {"masters": len(manifest["masters"]), "backup": str(backup),
            "lower_loop_files_unchanged": len(before["files"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=data.ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    staging = commands.add_parser("stage")
    staging.add_argument("--application", type=Path, required=True)
    staging.add_argument("--terminal-definitions", type=Path, required=True)
    staging.add_argument("--output", type=Path, required=True)
    staging.add_argument("--expected-terminals", type=int)
    staging.add_argument("--rustred-revision")
    staging.add_argument("--vakint-revision")
    staging.add_argument("--consumer-rustred-revision")
    installation = commands.add_parser("install")
    installation.add_argument("--staged", type=Path, required=True)
    installation.add_argument("--backup", type=Path, required=True)
    checking = commands.add_parser("validate")
    checking.add_argument("directory", type=Path)
    args = parser.parse_args()
    if args.command == "stage":
        result = stage(args.root, args.application, args.terminal_definitions, args.output,
                       args.expected_terminals, args.rustred_revision, args.vakint_revision,
                       args.consumer_rustred_revision)
    elif args.command == "install":
        result = install(args.root, args.staged, args.backup)
    else:
        result = {"masters": len(validate_stage(args.directory)["masters"])}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
