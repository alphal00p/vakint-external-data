#!/usr/bin/env python3
"""Build and validate the portable Vakint data contract using only Python stdlib."""

from __future__ import annotations

import argparse
import ast
import copy
import gzip
import hashlib
import json
import re
import shutil
import tarfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
ROOT_SCHEMA = "vakint.external-data.v1"
LOOP_SCHEMA = "vakint.external-data.loop.v1"
PRODUCER_SCHEMA = "vakint.external-data.producer-update.v1"
PRIMER_ROOTS = {1: 5, 2: 77, 3: 2320, 4: 164352}


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def file_record(path):
    return {"sha256": digest(path), "bytes": Path(path).stat().st_size}


def checked_path(base, relative):
    parts = PurePosixPath(relative).parts
    if (
        not parts
        or "\\" in relative
        or relative.startswith("/")
        or any(p in (".", "..") for p in relative.split("/"))
    ):
        raise ValueError(f"unsafe relative path: {relative}")
    path = base.joinpath(*parts)
    if path.is_symlink() or not path.resolve().is_relative_to(base.resolve()):
        raise ValueError(f"path escapes data root: {relative}")
    return path


def copy_verified(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if file_record(source) != file_record(destination):
            raise ValueError(
                f"refusing to replace different existing data: {destination}"
            )
    else:
        shutil.copy2(source, destination)
    if file_record(source) != file_record(destination):
        raise ValueError(f"migration checksum mismatch: {source}")


def migrate(source, vakint_source):
    source = Path(source).resolve()
    inventory = []
    for original in sorted(source.rglob("*")):
        if original.is_symlink():
            raise ValueError(f"source contains symlink: {original}")
        if not original.is_file():
            continue
        relative = original.relative_to(source)
        relocated = (
            Path("provenance/original-root") / relative
            if len(relative.parts) == 1
            else relative
        )
        copy_verified(original, ROOT / relocated)
        inventory.append(
            {
                "source": relative.as_posix(),
                "path": relocated.as_posix(),
                **file_record(original),
            }
        )
    copy_verified(
        Path(vakint_source) / "src/topologies/five_loop_data.rs",
        ROOT / "provenance/five_loop_data.rs",
    )
    write_json(
        ROOT / "provenance/migration.json",
        {
            "schema": "vakint.external-data.migration.v1",
            "source_tree": "vakint/artifacts",
            "files": inventory,
        },
    )
    print(f"Copied and hash-verified {len(inventory)} original files")


def five_loop_definitions():
    source = (ROOT / "provenance/five_loop_data.rs").read_text()
    momenta = ast.literal_eval(
        re.search(r"const MOMENTA:.*?= (\[.*?\n\]);", source, re.DOTALL)[1]
    )
    parents = []
    for block in re.findall(r"    Parent \{(.*?)\n    \}", source, re.DOTALL):
        parents.append(
            {
                "sector": int(re.search(r"sector: (\d+)", block)[1]),
                "vertices": ast.literal_eval(
                    re.search(r"vertices: (\[.*?\n        \]),", block, re.DOTALL)[1]
                ),
                "physical_slots": ast.literal_eval(
                    re.search(r"physical_slots: (\[[^]]*\])", block)[1]
                ),
            }
        )
    witnesses = []
    for block in re.findall(r"    Witness \{(.*?)\n    \}", source, re.DOTALL):
        witness = {
            k: int(re.search(rf"{k}: (\d+)", block)[1]) for k in ("sector", "parent")
        }
        for key in ("deleted_slots", "source_slots", "target_slots", "signs"):
            witness[key] = ast.literal_eval(
                re.search(rf"{key}: &(\[[^]]*\])", block)[1]
            )
        witness["routing"] = ast.literal_eval(
            re.search(r"routing: (\[.*?\n        \]),", block, re.DOTALL)[1]
        )
        witnesses.append(witness)
    if len(parents) != 4 or len(witnesses) != 67:
        raise ValueError("unexpected five-loop graph source format")
    for parent in parents:
        for vertex in parent["vertices"]:
            if any(
                sum(
                    (1 if slot > 0 else -1) * momenta[abs(slot) - 1][axis]
                    for slot in vertex
                )
                for axis in range(5)
            ):
                raise ValueError("five-loop parent violates momentum conservation")
    return momenta, parents, witnesses


def dot_quote(value):
    return json.dumps(str(value), ensure_ascii=False)


def parent_graph(parent, powers=None, witness=None, identity=""):
    """Contract absent edges; numerator factors stay in original common-basis slots."""
    vertices = parent["vertices"]
    edges = {
        slot: (
            next(i for i, v in enumerate(vertices) if slot + 1 in v),
            next(i for i, v in enumerate(vertices) if -slot - 1 in v),
        )
        for slot in parent["physical_slots"]
    }
    mapped = {slot: (slot, 1) for slot in parent["physical_slots"]}
    if powers is not None:
        mapped = {
            target: (source, powers[source])
            for source, target in zip(witness["source_slots"], witness["target_slots"])
            if powers[source] > 0
        }
    representative = list(range(len(vertices)))

    def find(i):
        while representative[i] != i:
            i = representative[i]
        return i

    for slot, (u, v) in edges.items():
        if slot not in mapped:
            representative[find(v)] = find(u)
    active = sorted({find(v) for edge in edges.values() for v in edge})
    lines = [
        "digraph topology {",
        "  graph [label="
        + dot_quote(identity or f"Five-loop maximal parent {parent['sector']}")
        + "];",
        "  edge [dir=none];",
    ]
    if powers is not None:
        lines.append(
            "  graph [family_powers="
            + dot_quote(json.dumps(powers))
            + ', common_basis_slots="zero-based", routing='
            + dot_quote(json.dumps(witness["routing"]))
            + "];"
        )
    for vertex in active:
        lines.append(f"  v{vertex} [label={dot_quote(vertex)}];")
    for slot, (source, power) in mapped.items():
        u, v = edges[slot]
        label = f"D{source + 1}" + (f"^{power}" if power != 1 else "")
        lines.append(
            f"  v{find(u)} -> v{find(v)} [label={dot_quote(label)}, common_basis_slot={source}, parent_slot={slot}, power={power}];"
        )
    if powers is not None:
        numerator = [[i, -p] for i, p in enumerate(powers) if p < 0]
        lines.append(
            "  graph [numerator_factors=" + dot_quote(json.dumps(numerator)) + "];"
        )
    lines.append("}")
    return "\n".join(lines) + "\n"


def generate_graphs(original):
    _, parents, witnesses = five_loop_definitions()
    atlas = [
        "digraph family {",
        '  graph [label="Five-loop common family: four maximal physical parents; slots are zero-based"];',
    ]
    for index, parent in enumerate(parents):
        relative = f"graphs/parent-{parent['sector']}.dot"
        path = ROOT / "5L" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(parent_graph(parent))
        body = parent_graph(parent).splitlines()[1:-1]
        atlas.append(f"  subgraph cluster_{index} {{")
        atlas.extend(
            "    " + re.sub(r"\bv(\d+)\b", rf"p{index}v\1", line) for line in body
        )
        atlas.append("  }")
    atlas.append("}")
    five_family = next(f for f in original["families"] if len(f["loop_momenta"]) == 5)
    (ROOT / "5L/graphs" / f"{five_family['sha256']}.dot").write_text(
        "\n".join(atlas) + "\n"
    )
    graph_references = {}
    for master in original["masters"]:
        if master["loop_count"] != 5:
            continue
        positive = {i for i, power in enumerate(master["powers"]) if power > 0}
        candidates = [w for w in witnesses if positive <= set(w["source_slots"])]
        if not candidates:
            raise ValueError(f"no physical graph witness for {master['master_id']}")
        witness = min(candidates, key=lambda w: (len(w["source_slots"]), w["sector"]))
        parent = parents[witness["parent"]]
        path = ROOT / master["directory"] / "graph.dot"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            parent_graph(parent, master["powers"], witness, master["master_id"])
        )
        graph_references[master["master_id"]] = f"graphs/parent-{parent['sector']}.dot"
    for family in original["families"]:
        loops = len(family["loop_momenta"])
        if loops == 5:
            continue
        masters = [
            m for m in original["masters"] if m["family_sha256"] == family["sha256"]
        ]
        maximal = max(
            masters,
            key=lambda m: (
                sum(p > 0 for p in m["powers"]),
                -sum(max(p, 0) for p in m["powers"]),
            ),
        )
        target = ROOT / f"{loops}L/graphs/{family['sha256']}.dot"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / maximal["directory"] / "graph.dot", target)
    from five_loop_graphs import generate_five_loop_graphs

    generate_five_loop_graphs(original)
    return graph_references


def relative_paths(value, loops):
    if isinstance(value, dict):
        return {key: relative_paths(item, loops) for key, item in value.items()}
    if isinstance(value, list):
        return [relative_paths(item, loops) for item in value]
    if isinstance(value, str) and value.startswith(f"{loops}L/"):
        return value[len(f"{loops}L/") :]
    return value


def coverage(loops):
    common = {
        "schema": "vakint.external-data.coverage.v1",
        "loop_count": loops,
        "complete_family_claim": False,
        "cache_completion_is_coverage_certificate": False,
    }
    if loops <= 3:
        return {
            **common,
            "kind": "native-closed",
            "authority": "Native ClosedArtifact replay certificate, restricted to its supported root domain",
            "certificate": {
                "path": "ibps/rules.rrbin",
                "predicate": "ClosedUnitMassProgram::validate_entry",
                "conjuncts": ["supported_root_power_bounds", "total_excess_scope"],
                "schema": "rustred-artifact-v6",
            },
        }
    if loops == 4:
        return {
            **common,
            "kind": "finite-tested-candidates",
            "authority": "Guarded descending native candidate rules; successful applications are pointwise results",
            "certified_domains": [],
            "evidence": "ibps/README.md",
            "known_master_basis_complete": False,
            "note": "Terminal catalog completeness is not arbitrary-index family closure. The completed finite cache workload does not strengthen certification.",
        }
    application = read_json(ROOT / "5L/ibps/application.json")
    return {
        **common,
        "kind": "saved-scope",
        "authority": application["metadata"]["authority"],
        "queries": "ibps/queries.json",
        "selection": "ibps/selection.json",
        "application": "ibps/application.json",
        "known_master_basis_complete": False,
        "metadata": application["metadata"],
        "note": "Recorded query predicates are preserved verbatim. Bounds over their union do not certify every integral with those ranks/powers; declared terminals have no computed coefficients.",
    }


def producer_coefficients(update, known, *, original_windows=False):
    """Read explicit capabilities; expression spelling never establishes exactness."""
    if (
        update.get("schema") != PRODUCER_SCHEMA
        or not isinstance(update.get("provenance"), dict)
        or not isinstance(update.get("masters"), dict)
    ):
        raise ValueError("unsupported producer update schema or structure")
    result = {}
    for identity, entry in update["masters"].items():
        if identity not in known or not isinstance(entry, dict):
            raise ValueError("unknown producer-update master identity")
        if entry.get("master_id", identity) != identity:
            raise ValueError("producer-update master identity disagrees with its key")
        rows = entry.get("coefficients")
        if not isinstance(rows, list) or not rows:
            raise ValueError("producer-update master needs coefficient records")
        coefficients = {}
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("invalid producer coefficient record")
            power = row.get("epsilon_power")
            symbolic, numerical = row.get("symbolic"), row.get("numerical")
            digits = row.get("significant_digits")
            if (
                type(power) is not int
                or type(symbolic) is not bool
                or type(numerical) is not bool
                or not (symbolic or numerical)
                or (numerical and (type(digits) is not int or digits < 1))
                or (not numerical and digits is not None)
            ):
                raise ValueError("invalid producer coefficient capability")
            if power in coefficients:
                raise ValueError("duplicate producer coefficient power")
            if original_windows:
                first, last = known[identity]["epsilon_range"]
                if not first <= power <= last:
                    raise ValueError(
                        "producer updates cannot replace supplemented orders"
                    )
            coefficients[power] = {
                "epsilon_power": power,
                "symbolic": symbolic,
                "numerical": numerical,
                "significant_digits": digits,
            }
        result[identity] = coefficients
    return result


def check_producer_payload(entry, master, coefficients, symbolic, numerical, root=ROOT):
    for power, item in coefficients.items():
        if item["symbolic"] and power not in symbolic:
            raise ValueError("producer exact coefficient has no symbolic payload")
        if item["numerical"] != (power in numerical):
            raise ValueError("producer numerical availability disagrees with payload")
        if (
            not item["symbolic"]
            and power in symbolic
            and symbolic[power] != numerical[power]
        ):
            raise ValueError("producer update would discard a symbolic expression")
    files = entry.get("files", {})
    if not isinstance(files, dict):
        raise ValueError("invalid producer payload file bindings")
    for name, expected in files.items():
        if name not in master["files"]:
            raise ValueError("producer payload file binding differs from master")
        if expected != master["files"][name]:
            from graph_migration import accepts_producer_binding
            from precision_supplement import (
                accepts_producer_binding as accepts_precision_binding,
            )

            accepted = (
                accepts_producer_binding(expected, master, root)
                if name == "graph.dot"
                else accepts_precision_binding(expected, master, name, root)
            )
            if not accepted:
                raise ValueError("producer payload file binding differs from master")


def generate(version):
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?", version):
        raise ValueError("version must be an immutable vMAJOR.MINOR.PATCH tag")
    original = read_json(ROOT / "provenance/original-root/manifest.json")
    from graph_migration import RECEIPT
    from graph_migration import validate as validate_graph_migration

    if (ROOT / RECEIPT).exists():
        validate_graph_migration()
    producer_path = ROOT / "provenance/producer-update.json"
    producer = read_json(producer_path) if producer_path.exists() else None
    known = {master["master_id"]: master for master in original["masters"]}
    updates = (
        producer_coefficients(producer, known, original_windows=True)
        if producer is not None
        else {}
    )
    import precision_supplement
    from finite_constants import (
        binding as constant_binding,
    )
    from finite_constants import (
        validate_source as validate_constant_source,
    )

    validate_constant_source(ROOT)

    precision_update = precision_supplement.load_source(ROOT)
    precision_updates = precision_supplement.coefficients(precision_update, known)
    supplement_path = ROOT / "provenance/coefficient-supplement.json"
    supplement = read_json(supplement_path) if supplement_path.exists() else None
    supplements = {}
    if supplement is not None:
        if supplement["schema"] != "vakint.external-data.coefficient-supplement.v1":
            raise ValueError("unsupported coefficient supplement schema")
        for entry in supplement["masters"]:
            name = entry["master_id"]
            if name not in known or name in supplements:
                raise ValueError("unknown or duplicate supplemented master")
            coefficients = {c["epsilon_power"]: c for c in entry["coefficients"]}
            if len(coefficients) != len(entry["coefficients"]):
                raise ValueError("duplicate supplemented coefficient")
            supplements[name] = coefficients
    parent_graphs = generate_graphs(original)
    loop_packs = []
    for loops in range(1, 6):
        directory = ROOT / f"{loops}L"
        loop_precision = precision_supplement.loop_slice(precision_update, loops)
        if loop_precision is not None:
            write_json(directory / precision_supplement.LOOP_RECEIPT, loop_precision)
        families = []
        for family in original["families"]:
            if len(family["loop_momenta"]) != loops:
                continue
            record = copy.deepcopy(family)
            record["graph"] = f"graphs/{family['sha256']}.dot"
            record["aliases"] = sorted(
                {
                    m["alias"]
                    for m in original["masters"]
                    if m["family_sha256"] == family["sha256"]
                }
            )
            families.append(record)
        masters = []
        for master in original["masters"]:
            if master["loop_count"] != loops:
                continue
            record = relative_paths(copy.deepcopy(master), loops)
            record["model"] = "model.json"
            record["kind"] = (
                "known-master"
                if master["status"] == "accepted"
                else "uncomputed-terminal"
            )
            record["parent_graph"] = parent_graphs.get(
                master["master_id"], f"graphs/{master['family_sha256']}.dot"
            )
            record.setdefault("files", {})
            graph = directory / record["directory"] / "graph.dot"
            record["files"]["graph.dot"] = {
                "path": graph.relative_to(directory).as_posix(),
                "sha256": digest(graph),
            }
            for file in record["files"].values():
                file["sha256"] = digest(checked_path(directory, file["path"]))
            symbolic = (
                read_json(directory / record["files"]["symbolic.json"]["path"])
                if "symbolic.json" in record["files"]
                else []
            )
            numerical = (
                read_json(directory / record["files"]["numerical.json"]["path"])
                if "numerical.json" in record["files"]
                else []
            )
            symbolic_powers, numerical_powers = (
                set(master.get("symbolic_powers", [])),
                {p for p, _ in numerical},
            )
            added = supplements.get(master["master_id"], {})
            original_range = set(
                range(master["epsilon_range"][0], master["epsilon_range"][1] + 1)
            )
            if set(added) & original_range:
                raise ValueError(
                    "coefficient supplements must extend, not overwrite, original orders"
                )
            symbolic_powers.update(
                power for power, item in added.items() if item["symbolic"]
            )
            if not symbolic_powers <= {p for p, _ in symbolic}:
                raise ValueError("declared exact coefficient has no symbolic payload")
            powers = sorted(symbolic_powers | numerical_powers)
            if set(powers) - original_range != set(added):
                raise ValueError(
                    "new coefficient payloads require an explicit validated supplement"
                )
            for power, item in added.items():
                if item["symbolic"] != (power in symbolic_powers) or item[
                    "numerical"
                ] != (power in numerical_powers):
                    raise ValueError(
                        "supplement availability disagrees with coefficient payloads"
                    )
            record["available_epsilon_powers"] = powers
            capabilities = {
                power: {
                    "epsilon_power": power,
                    "symbolic": power in symbolic_powers,
                    "numerical": power in numerical_powers,
                    "significant_digits": added.get(power, {}).get(
                        "significant_digits", master.get("significant_digits")
                    )
                    if power in numerical_powers
                    else None,
                }
                for power in powers
            }
            changed = updates.get(master["master_id"], {})
            if changed:
                check_producer_payload(
                    producer["masters"][master["master_id"]],
                    record,
                    changed,
                    dict(symbolic),
                    dict(numerical),
                )
                capabilities.update(changed)
                symbolic_powers = {
                    power for power, item in capabilities.items() if item["symbolic"]
                }
                powers = sorted(capabilities)
                record["symbolic_powers"] = sorted(symbolic_powers)
                record["producer_update"] = "producer-update.json"
                digits = [
                    item["significant_digits"]
                    for item in capabilities.values()
                    if item["numerical"]
                ]
                record["significant_digits"] = min(digits) if digits else None
            precision_changed = precision_updates.get(master["master_id"], {})
            if precision_changed:
                for power, row in precision_changed.items():
                    if (
                        power not in capabilities
                        or row["symbolic"] != capabilities[power]["symbolic"]
                    ):
                        raise ValueError(
                            "numerical precision upgrade cannot add orders or change symbolic availability"
                        )
                    capabilities[power] = row
                precision_supplement.validate_master(precision_update, record, ROOT)
                record["numerical_precision_supplement"] = (
                    precision_supplement.LOOP_RECEIPT
                )
                record["significant_digits"] = min(
                    row["significant_digits"]
                    for row in capabilities.values()
                    if row["numerical"]
                )
            record["coefficients"] = [capabilities[power] for power in powers]
            record["available_epsilon_powers"] = powers
            record["kind"] = "known-master" if powers else "uncomputed-terminal"
            if added:
                record["symbolic_powers"] = sorted(symbolic_powers)
                record["epsilon_range"] = [min(powers), max(powers)]
                record["coefficient_supplement"] = "coefficient-supplement.json"
                record.get("fastsecdec_configuration", {}).get("generation", {})[
                    "order"
                ] = max(powers)
            masters.append(record)
        loop_updates = {
            identity: entry
            for identity, entry in (producer or {}).get("masters", {}).items()
            if known[identity]["loop_count"] == loops
        }
        if loop_updates:
            write_json(
                directory / "producer-update.json",
                {
                    **{
                        key: value
                        for key, value in producer.items()
                        if key != "masters"
                    },
                    "masters": loop_updates,
                },
            )
        supplemented = [m for m in masters if m["master_id"] in supplements]
        if supplemented:
            loop_provenance = supplement["provenance"]
            if campaigns := loop_provenance.get("campaigns"):
                applicable = [
                    campaign
                    for campaign in campaigns.values()
                    if loops in campaign["loop_counts"]
                ]
                if len(applicable) != 1:
                    raise ValueError(
                        "supplemented loop must have one provenance campaign"
                    )
                loop_provenance = applicable[0]
            write_json(
                directory / "coefficient-supplement.json",
                {
                    **{
                        key: value
                        for key, value in supplement.items()
                        if key not in ("masters", "provenance")
                    },
                    "provenance": loop_provenance,
                    "masters": [
                        entry
                        for entry in supplement["masters"]
                        if entry["master_id"] in {m["master_id"] for m in supplemented}
                    ],
                },
            )
        write_json(directory / "coverage.json", coverage(loops))
        cache = {"available": False}
        if loops <= 4:
            metadata = read_json(directory / "cache.json")
            report = metadata["preparation_report"]
            cache = {
                "available": True,
                "path": "cache",
                "metadata": "cache.json",
                "status": report["status"],
                "total_roots": report["total_roots"],
                "completed_roots": report["completed_roots"],
                "binding_ids": sorted(
                    p.name for p in (directory / "cache/bindings").iterdir()
                ),
                "newly_stored_intermediates": report["newly_stored_intermediates"],
                "capture_metadata_exhausted_roots": report[
                    "capture_metadata_exhausted_roots"
                ],
            }
        kind = (
            "closed"
            if loops <= 3
            else "candidate"
            if loops == 4
            else "saved-application"
        )
        manifest = {
            "schema": LOOP_SCHEMA,
            "version": version,
            "loop_count": loops,
            "dimension": original["dimension"],
            "normalization": original["normalization"],
            "unit_mass_squared": True,
            "families": families,
            "masters": masters,
            "ibps": {
                "kind": kind,
                "path": "ibps",
                "files": sorted(
                    p.relative_to(directory).as_posix()
                    for p in (directory / "ibps").rglob("*")
                    if p.is_file()
                ),
            },
            "cache": cache,
            "coverage": "coverage.json",
            "provenance": {
                "master_producer_rustred_revision": original["rustred_revision"],
                "vakint_reference_revision": original["vakint_reference_revision"],
                "native_cache_rustred_revision": read_json(directory / "cache.json")[
                    "RustRed_revision"
                ]
                if loops <= 4
                else None,
            },
            "files": {
                p.relative_to(directory).as_posix(): file_record(p)
                for p in sorted(directory.rglob("*"))
                if p.is_file() and p != directory / "manifest.json"
            },
        }
        if loop_updates:
            manifest["producer_update"] = "producer-update.json"
        if loop_precision is not None:
            manifest["numerical_precision_supplement"] = (
                precision_supplement.LOOP_RECEIPT
            )
        if constants := constant_binding(directory):
            manifest["constant_bindings"] = constants
        write_json(directory / "manifest.json", manifest)
        loop_packs.append(
            {
                "loop_count": loops,
                "manifest": f"{loops}L/manifest.json",
                "manifest_sha256": digest(directory / "manifest.json"),
                "archive": f"vakint-external-data-{version}-{loops}L.tar.gz",
                "archive_sha256": None,
                "archive_bytes": None,
            }
        )
    write_json(
        ROOT / "manifest.json",
        {"schema": ROOT_SCHEMA, "version": version, "loop_packs": loop_packs},
    )
    migration_path = ROOT / "provenance/migration.json"
    migration = read_json(migration_path)
    for item in migration["files"]:
        path = checked_path(ROOT, item["path"])
        if file_record(path) != {key: item[key] for key in ("sha256", "bytes")}:
            preserved = next(
                (
                    relative / item["source"]
                    for relative in (
                        Path("provenance/original-coefficients"),
                        Path("provenance/native-graphs/original"),
                    )
                    if (ROOT / relative / item["source"]).exists()
                    and file_record(ROOT / relative / item["source"])
                    == {key: item[key] for key in ("sha256", "bytes")}
                ),
                None,
            )
            if preserved is None:
                raise ValueError(
                    f"original payload was not preserved: {item['source']}"
                )
            item["path"] = preserved.as_posix()
    write_json(migration_path, migration)
    print(f"Generated {version} metadata for all five loop packs")


def validate(root=None):
    root = ROOT if root is None else root
    from finite_constants import (
        binding as constant_binding,
    )
    from finite_constants import (
        validate_source as validate_constant_source,
    )
    from graph_migration import RECEIPT
    from graph_migration import validate as validate_graph_migration
    from precision_supplement import load_source as validate_precision_source

    if (root / RECEIPT).exists():
        validate_graph_migration(root)
    validate_precision_source(root)
    validate_constant_source(root)
    manifest = read_json(root / "manifest.json")
    if manifest["schema"] != ROOT_SCHEMA:
        raise ValueError("unsupported root schema")
    if [p["loop_count"] for p in manifest["loop_packs"]] != list(range(1, 6)):
        raise ValueError("release must contain disjoint 1L through 5L packs")
    counts = []
    for pack in manifest["loop_packs"]:
        path = checked_path(root, pack["manifest"])
        if digest(path) != pack["manifest_sha256"]:
            raise ValueError(f"loop manifest checksum mismatch: {path}")
        loop = read_json(path)
        if (
            loop["schema"] != LOOP_SCHEMA
            or loop["version"] != manifest["version"]
            or loop["loop_count"] != pack["loop_count"]
        ):
            raise ValueError(f"loop manifest identity mismatch: {path}")
        entries = list(path.parent.rglob("*"))
        if any(p.is_symlink() for p in entries):
            raise ValueError("loop payload contains a symlink")
        actual = {
            p.relative_to(path.parent).as_posix()
            for p in entries
            if p.is_file() and p != path
        }
        if actual != set(loop["files"]):
            raise ValueError(f"loop file inventory differs: {path}")
        for name, expected in loop["files"].items():
            if file_record(checked_path(path.parent, name)) != expected:
                raise ValueError(f"payload checksum/size mismatch: {name}")
        if loop.get("constant_bindings") != constant_binding(path.parent):
            raise ValueError(
                "finite constant manifest binding differs from its payload"
            )
        for master in loop["masters"]:
            for value in master["files"].values():
                if digest(checked_path(path.parent, value["path"])) != value["sha256"]:
                    raise ValueError(
                        f"master file checksum mismatch: {master['master_id']}"
                    )
            symbolic = (
                read_json(path.parent / master["files"]["symbolic.json"]["path"])
                if "symbolic.json" in master["files"]
                else []
            )
            numerical = (
                read_json(path.parent / master["files"]["numerical.json"]["path"])
                if "numerical.json" in master["files"]
                else []
            )
            symbolic_powers, numerical_powers = (
                set(master.get("symbolic_powers", [])),
                {p for p, _ in numerical},
            )
            if not symbolic_powers <= {p for p, _ in symbolic}:
                raise ValueError("declared exact coefficient has no symbolic payload")
            if len({p for p, _ in symbolic}) != len(symbolic) or len(
                numerical_powers
            ) != len(numerical):
                raise ValueError("duplicate epsilon coefficient")
            for coefficient in master["coefficients"]:
                power = coefficient["epsilon_power"]
                if coefficient["symbolic"] != (power in symbolic_powers) or coefficient[
                    "numerical"
                ] != (power in numerical_powers):
                    raise ValueError("coefficient availability disagrees with payload")
                if coefficient["numerical"] and (
                    not isinstance(coefficient["significant_digits"], int)
                    or coefficient["significant_digits"] < 1
                ):
                    raise ValueError(
                        "numerical coefficient lacks validated significant digits"
                    )
            if master["available_epsilon_powers"] != sorted(
                symbolic_powers | numerical_powers
            ):
                raise ValueError("coefficient power inventory differs")
            if master["kind"] == "uncomputed-terminal" and master["coefficients"]:
                raise ValueError(
                    "uncomputed terminal advertises available coefficients"
                )
            checked_path(path.parent, master["parent_graph"]).read_bytes()
        from precision_supplement import validate_loop as validate_precision_loop

        precision_updates = validate_precision_loop(path.parent, loop["masters"])
        for identity, rows in precision_updates.items():
            master = next(
                master for master in loop["masters"] if master["master_id"] == identity
            )
            actual = {row["epsilon_power"]: row for row in master["coefficients"]}
            if any(actual.get(power) != row for power, row in rows.items()):
                raise ValueError(
                    "numerical precision capabilities disagree with loop manifest"
                )
        if update_path := loop.get("producer_update"):
            update = read_json(checked_path(path.parent, update_path))
            known = {master["master_id"]: master for master in loop["masters"]}
            for identity, coefficients in producer_coefficients(update, known).items():
                master = known[identity]
                coefficients.update(precision_updates.get(identity, {}))
                actual = {
                    item["epsilon_power"]: item for item in master["coefficients"]
                }
                if any(
                    actual.get(power) != item for power, item in coefficients.items()
                ):
                    raise ValueError(
                        "producer capabilities disagree with loop manifest"
                    )
                symbolic = (
                    read_json(path.parent / master["files"]["symbolic.json"]["path"])
                    if "symbolic.json" in master["files"]
                    else []
                )
                numerical = (
                    read_json(path.parent / master["files"]["numerical.json"]["path"])
                    if "numerical.json" in master["files"]
                    else []
                )
                check_producer_payload(
                    update["masters"][identity],
                    master,
                    coefficients,
                    dict(symbolic),
                    dict(numerical),
                    root,
                )
        if loop["cache"]["available"]:
            metadata = read_json(path.parent / loop["cache"]["metadata"])
            report = metadata["preparation_report"]
            if (
                report["status"] != "complete"
                or report["completed_roots"] != PRIMER_ROOTS[loop["loop_count"]]
                or report["total_roots"] != report["completed_roots"]
                or report["failure"] is not None
            ):
                raise ValueError("cache is not a complete finite primer")
            for name, checksum in metadata["files_sha256"].items():
                if digest(checked_path(path.parent / "cache", name)) != checksum:
                    raise ValueError("native cache differs from producer receipt")
            bundle = (path.parent / "cache/bundle.rrindex").read_bytes()
            for binding in loop["cache"]["binding_ids"]:
                if bytes.fromhex(binding) not in bundle:
                    raise ValueError("cache binding absent from native bundle index")
            if (
                loop["loop_count"] <= 3
                and bytes.fromhex(digest(path.parent / "ibps/rules.rrbin"))
                not in bundle
            ):
                raise ValueError("sealed program digest absent from cache binding")
        counts.append(
            {
                "loop_count": loop["loop_count"],
                "files": len(loop["files"]),
                "masters": len(loop["masters"]),
                "cache": loop["cache"]["available"],
            }
        )
    migration = root / "provenance/migration.json"
    if migration.exists():
        for item in read_json(migration)["files"]:
            if file_record(checked_path(root, item["path"])) != {
                k: item[k] for k in ("sha256", "bytes")
            }:
                raise ValueError(f"original migrated payload changed: {item['path']}")
    evidence = root / "validation/manifest.json"
    if evidence.exists():
        for item in read_json(evidence)["files"]:
            path = checked_path(evidence.parent, item["path"])
            if file_record(path) != {key: item[key] for key in ("sha256", "bytes")}:
                raise ValueError("compressed validation evidence checksum mismatch")
            with gzip.open(path, "rb") as stream:
                raw = stream.read(item["uncompressed_bytes"] + 1)
            if (
                len(raw) != item["uncompressed_bytes"]
                or hashlib.sha256(raw).hexdigest() != item["uncompressed_sha256"]
            ):
                raise ValueError("original validation evidence checksum mismatch")
    print(json.dumps({"version": manifest["version"], "validated": counts}))
    return manifest


def pack(output):
    manifest = validate()
    output = Path(output).resolve()
    if output.is_relative_to(ROOT):
        raise ValueError("release outputs must be outside the source repository")
    output.mkdir(parents=True, exist_ok=True)
    for loop in manifest["loop_packs"]:
        target = output / loop["archive"]
        with (
            target.open("wb") as raw,
            gzip.GzipFile(
                filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9
            ) as gz,
            tarfile.open(fileobj=gz, mode="w|", format=tarfile.USTAR_FORMAT) as archive,
        ):
            directory = ROOT / f"{loop['loop_count']}L"
            for source in [directory, *sorted(directory.rglob("*"))]:
                info = archive.gettarinfo(
                    str(source), arcname=source.relative_to(ROOT).as_posix()
                )
                info.uid = info.gid = info.mtime = 0
                info.uname = info.gname = ""
                info.mode = 0o755 if info.isdir() else 0o644
                if source.is_file():
                    with source.open("rb") as stream:
                        archive.addfile(info, stream)
                else:
                    archive.addfile(info)
        loop["archive_sha256"] = digest(target)
        loop["archive_bytes"] = target.stat().st_size
        print(
            json.dumps(
                {
                    "archive": str(target),
                    "bytes": target.stat().st_size,
                    "sha256": loop["archive_sha256"],
                }
            ),
            flush=True,
        )
    write_json(output / "manifest.json", manifest)
    (output / "SHA256SUMS").write_text(
        "".join(
            f"{digest(p)}  {p.name}\n"
            for p in sorted(output.iterdir())
            if p.name == "manifest.json"
            or p.name in {x["archive"] for x in manifest["loop_packs"]}
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    migration = commands.add_parser("migrate")
    migration.add_argument("--source", type=Path, required=True)
    migration.add_argument("--vakint-source", type=Path, required=True)
    generation = commands.add_parser("generate")
    generation.add_argument("--version", required=True)
    commands.add_parser("validate")
    packing = commands.add_parser("pack")
    packing.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "migrate":
        migrate(args.source, args.vakint_source)
    elif args.command == "generate":
        generate(args.version)
    elif args.command == "validate":
        validate()
    elif args.command == "pack":
        pack(args.output)


if __name__ == "__main__":
    main()
