#!/usr/bin/env python3
"""Generate model-resolved five-loop graphs from the authenticated census."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from collections import Counter
from fractions import Fraction
from pathlib import Path

import data


def inverse(matrix):
    size = len(matrix)
    rows = [
        [Fraction(value) for value in row] + [Fraction(i == j) for j in range(size)]
        for i, row in enumerate(matrix)
    ]
    for column in range(size):
        pivot = next((i for i in range(column, size) if rows[i][column]), None)
        if pivot is None:
            raise ValueError("five-loop graph chord coordinates are singular")
        rows[column], rows[pivot] = rows[pivot], rows[column]
        scale = rows[column][column]
        rows[column] = [entry / scale for entry in rows[column]]
        for i in range(size):
            if i != column:
                scale = rows[i][column]
                rows[i] = [a - scale * b for a, b in zip(rows[i], rows[column])]
    result = [row[size:] for row in rows]
    if any(value.denominator != 1 for row in result for value in row):
        raise ValueError("five-loop graph coordinates are not unimodular")
    return [[int(value) for value in row] for row in result]


def multiply(left, right):
    return [
        [sum(a * b for a, b in zip(row, column)) for column in zip(*right)]
        for row in left
    ]


def disjoint_sets(size):
    representatives = list(range(size))

    def find(vertex):
        while representatives[vertex] != vertex:
            vertex = representatives[vertex]
        return vertex

    def join(source, target):
        source, target = find(source), find(target)
        if source == target:
            return False
        representatives[target] = source
        return True

    return find, join


def denominator(row):
    """Minkowski D=q²-m² in native Spenso scalar-product notation."""
    terms = ["-UFO::mUV^2"]
    for i, left in enumerate(row):
        for j in range(i, len(row)):
            coefficient = left * row[j] * (1 if i == j else 2)
            if coefficient:
                arguments = ",".join(
                    f"FeynKit::LoopMomentum({axis},spenso::mink(gammalooprs::dim))"
                    for axis in (i, j)
                )
                terms.append(f"({coefficient})*spenso::dot({arguments})")
    return "(" + "+".join(terms) + ")"


def select_witness(master, witnesses):
    positive = {i for i, power in enumerate(master["powers"]) if power > 0}
    candidates = [w for w in witnesses if positive <= set(w["source_slots"])]
    return min(candidates, key=lambda w: (len(w["source_slots"]), w["sector"]))


def canonical_graph(master, momenta, parents, witnesses, fingerprint):
    """Retain the census witness while choosing actual graph chords as coordinates.

    A source-family momentum transforms by ``witness.routing`` into the parent
    coordinates. The chord-row inverse then expresses it in the graph's unit
    loop coordinates. Negative source powers become the complete D=q²-m²
    numerator factors, not just momentum squares.
    """
    powers = master["powers"]
    witness = select_witness(master, witnesses)
    parent = parents[witness["parent"]]
    vertices = parent["vertices"]
    endpoints = {
        slot: (
            next(i for i, v in enumerate(vertices) if slot + 1 in v),
            next(i for i, v in enumerate(vertices) if -slot - 1 in v),
        )
        for slot in parent["physical_slots"]
    }
    physical = {
        target: (source, powers[source], sign)
        for source, target, sign in zip(
            witness["source_slots"], witness["target_slots"], witness["signs"]
        )
        if powers[source] > 0
    }
    find, join = disjoint_sets(len(vertices))
    for slot, (source, target) in endpoints.items():
        if slot not in physical:
            join(source, target)
    active = sorted({find(v) for slot in physical for v in endpoints[slot]})
    vertex_ids = {vertex: i for i, vertex in enumerate(active)}
    edges = [
        {
            "source": vertex_ids[find(endpoints[target][0])],
            "target": vertex_ids[find(endpoints[target][1])],
            "parent_slot": target,
            "common_basis_slot": source,
            "power": power,
            "source_momentum_sign": sign,
        }
        for target, (source, power, sign) in sorted(physical.items())
    ]
    _, join = disjoint_sets(len(active))
    tree, loops = [], []
    for edge_id, edge in enumerate(edges):
        (tree if join(edge["source"], edge["target"]) else loops).append(edge_id)
    if len(loops) != 5:
        raise ValueError(f"{master['master_id']}: contraction changed loop count")
    chord_rows = [momenta[edges[i]["parent_slot"]] for i in loops]
    parent_to_chords = inverse(chord_rows)
    common_to_chords = multiply(witness["routing"], parent_to_chords)
    source_rows = multiply(momenta, common_to_chords)
    signatures = multiply(
        [momenta[edge["parent_slot"]] for edge in edges], parent_to_chords
    )
    for edge, signature in zip(edges, signatures):
        expected = [edge["source_momentum_sign"] * value for value in signature]
        if source_rows[edge["common_basis_slot"]] != expected:
            raise ValueError("common-basis witness does not preserve an edge momentum")
    balance = [[0] * 5 for _ in active]
    slots = Counter()
    for edge, signature in zip(edges, signatures):
        for axis, value in enumerate(signature):
            balance[edge["source"]][axis] += value
            balance[edge["target"]][axis] -= value
        edge["source_slot"] = slots[edge["source"]]
        slots[edge["source"]] += 1
        edge["target_slot"] = slots[edge["target"]]
        slots[edge["target"]] += 1
    if any(any(row) for row in balance):
        raise ValueError("contracted graph violates momentum conservation")
    if any(degree < 2 or degree > 10 for degree in slots.values()):
        raise ValueError("contracted graph exceeds the authenticated scalar model")
    numerator_factors = [[i, -power] for i, power in enumerate(powers) if power < 0]
    numerator = (
        "*".join(
            f"{denominator(source_rows[slot])}^{power}"
            for slot, power in numerator_factors
        )
        or "1"
    )
    basis = {
        "tree_edges": tree,
        "loop_edges": loops,
        "external_edges": [],
        "dependent_externals": [],
        "edge_signatures": {
            str(i): {"loops": signature, "external": []}
            for i, signature in enumerate(signatures)
        },
    }
    half_edges = [
        {"edge": i, "endpoint": endpoint}
        for i in range(len(edges))
        for endpoint in ("source", "target")
    ]
    attrs = {
        "feynkit_name": master["master_id"],
        "model_fingerprint": fingerprint,
        "symmetry_factor": 1,
        "overall_factor": "1",
        "numerator": numerator,
        "numerator_prefactor": "1",
        "projector": "1",
        "loop_momentum_edges": ",".join(map(str, loops)),
        "loop_momentum_basis": json.dumps(basis, separators=(",", ":")),
        "half_edge_order": json.dumps(half_edges, separators=(",", ":")),
        "cuts": "[]",
        "topology_threshold_candidates": "[]",
        "family_powers": json.dumps(powers),
        "common_basis_slots": "zero-based",
        "routing": json.dumps(witness["routing"]),
        "common_basis_to_graph_loops": json.dumps(common_to_chords),
        "parent_sector": parent["sector"],
        "census_sector": witness["sector"],
        "numerator_factors": json.dumps(numerator_factors),
    }

    def attributes(values):
        return ", ".join(
            f"{key}={value if isinstance(value, int) else data.dot_quote(value)}"
            for key, value in values.items()
        )

    lines = ["digraph feynkit {", f"  graph [{attributes(attrs)}];"]
    for vertex in range(len(active)):
        degree = slots[vertex]
        vertex_attrs = {
            "id": vertex,
            "feynkit_name": f"v{active[vertex]}",
            "interaction_id": degree - 2,
            "interaction": f"V_SCALAR{degree}",
            "numerator": numerator if vertex == 0 else "1",
        }
        lines.append(f"  v{vertex} [{attributes(vertex_attrs)}];")
    for edge_id, edge in enumerate(edges):
        edge_attrs = {
            "id": edge_id,
            "particle_id": 0,
            "pdg": 9000001,
            "particle": "phi",
            "directed": "false",
            "source_slot": edge["source_slot"],
            "target_slot": edge["target_slot"],
            "dir": "none",
            "numerator": "1",
            "power": edge["power"],
            "common_basis_slot": edge["common_basis_slot"],
            "parent_slot": edge["parent_slot"],
            "source_momentum_sign": edge["source_momentum_sign"],
        }
        if edge_id in loops:
            edge_attrs["lmb_id"] = loops.index(edge_id)
        lines.append(
            f"  v{edge['source']} -> v{edge['target']} [{attributes(edge_attrs)}];"
        )
    lines.append("}")
    return "\n".join(lines) + "\n"


def generate_five_loop_graphs(original, root=data.ROOT, check=False):
    momenta, parents, witnesses = data.five_loop_definitions()
    family = next(f for f in original["families"] if len(f["loop_momenta"]) == 5)
    if len(family["denominators"]) != len(momenta):
        raise ValueError("five-loop common family has an unexpected size")
    for denominator_definition, momentum in zip(family["denominators"], momenta):
        expected = [
            momentum[coordinate["left"]]
            * momentum[coordinate["right"]]
            * (1 if coordinate["left"] == coordinate["right"] else 2)
            for coordinate in family["coordinates"]
            if coordinate["kind"] == "loop_loop"
        ]
        if (
            list(map(Fraction, denominator_definition["coefficients"])) != expected
            or Fraction(denominator_definition["constant"]) != -1
        ):
            raise ValueError(
                "five-loop census and authenticated family denominators differ"
            )
    root = Path(root)
    # All 905 contractions have valence <=10; reuse the existing scalar model.
    model = root / "4L/model.json"
    fingerprint = re.search(
        r'model_fingerprint="([0-9a-f]{64})"',
        (root / "4L/masters/P1/graph.dot").read_text(),
    )[1]
    records = []
    for master in original["masters"]:
        if master["loop_count"] != 5:
            continue
        path = root / master["directory"] / "graph.dot"
        archive = (
            root
            / "provenance/five-loop-graphs/original"
            / Path(master["directory"]).relative_to("5L")
            / "graph.dot"
        )
        witness = select_witness(master, witnesses)
        expected_original = data.parent_graph(
            parents[witness["parent"]], master["powers"], witness, master["master_id"]
        )
        canonical = canonical_graph(master, momenta, parents, witnesses, fingerprint)
        if check:
            if (
                path.read_text() != canonical
                or archive.read_text() != expected_original
            ):
                raise ValueError(f"canonical five-loop graph mismatch: {path}")
        else:
            if archive.exists() and archive.read_text() != expected_original:
                raise ValueError(f"different archived original: {archive}")
            if not archive.exists():
                if path.exists() and path.read_text() != expected_original:
                    raise ValueError(f"original five-loop graph differs: {path}")
                archive.parent.mkdir(parents=True, exist_ok=True)
                archive.write_text(expected_original)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(canonical)
        records.append(
            {
                "master_id": master["master_id"],
                "path": str(path.relative_to(root)),
                "original": str(archive.relative_to(root)),
                "original_sha256": data.digest(archive),
                "canonical_sha256": data.digest(path),
            }
        )
    target_model = root / "5L/model.json"
    if check:
        if model.read_bytes() != target_model.read_bytes():
            raise ValueError("five-loop scalar model differs from the source model")
    else:
        shutil.copyfile(model, target_model)
        data.write_json(
            root / "provenance/five-loop-graphs/migration.json",
            {
                "schema": "vakint.external-data.graph-migration.v1",
                "source": "provenance/five_loop_data.rs",
                "source_sha256": data.digest(root / "provenance/five_loop_data.rs"),
                "model": "5L/model.json",
                "model_fingerprint": fingerprint,
                "graphs": records,
            },
        )
    return len(records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    count = generate_five_loop_graphs(
        data.read_json(data.ROOT / "provenance/original-root/manifest.json"),
        check=arguments.check,
    )
    print(
        f"{'Validated' if arguments.check else 'Generated'} {count} canonical five-loop graphs"
    )
