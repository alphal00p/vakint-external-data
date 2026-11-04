import copy
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import data
import model_identity


class NativeGraphIdentityTests(unittest.TestCase):
    def test_installed_projection_preserves_models_and_matches_all_native_graphs(self):
        context = model_identity.validate(data.ROOT)
        self.assertEqual(len(context["receipt"]["graphs"]), 763)
        self.assertEqual(len(context["native_graphs"]), 763)
        self.assertEqual(len(context["models"]), 2)
        self.assertEqual(len(context["expressions"]), 147)
        for path, native in context["native_graphs"].items():
            migrated = context["receipt"]["graphs"][path]
            self.assertEqual(migrated["original"]["sha256"], native["source_sha256"])
            self.assertEqual(migrated["current_sha256"], native["migrated_sha256"])

    def test_transform_changes_only_native_identity_and_verified_numerator_attributes(
        self,
    ):
        old, new = "a" * 64, "b" * 64
        source = (
            f'digraph {{ graph [model_fingerprint="{old}", numerator="old(x)", projector="1"];\n'
            ' a -> b [power=3,lmb_id=0,numerator="1"]; }\n'
        )
        result = model_identity.transform_dot(source, old, new, {"old(x)": "new(x)"})
        self.assertEqual(
            result,
            source.replace(old, new).replace(
                'numerator="old(x)"', 'numerator="new(x)"'
            ),
        )
        with self.assertRaisesRegex(ValueError, "old model"):
            model_identity.transform_dot(source, new, old, {})
        unknown = source.replace("old(x)", "FeynKit::LoopMomentum(0)")
        with self.assertRaisesRegex(ValueError, "mapping"):
            model_identity.transform_dot(unknown, old, new, {})
        misplaced = source.replace('projector="1"', 'label="FeynKit::LoopMomentum(0)"')
        with self.assertRaisesRegex(ValueError, "outside"):
            model_identity.transform_dot(misplaced, old, new, {})

    def test_old_hash_adapter_rejects_geometry_edits_even_with_updated_outer_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = (
                'digraph { graph [model_fingerprint="'
                + "a" * 64
                + '"]; a -> b [power=2]; }\n'
            )
            (root / "original.dot").write_text(original)
            migrated = original.replace("a" * 64, "b" * 64)
            path = root / "current.dot"
            path.write_text(migrated)
            old_sha, new_sha = (
                hashlib.sha256(value.encode()).hexdigest()
                for value in (original, migrated)
            )
            row = {
                "original": {
                    "path": "original.dot",
                    **data.file_record(root / "original.dot"),
                },
                "current_sha256": new_sha,
                "model_source_sha256": "model",
            }
            context = {
                "receipt": {"graphs": {"current.dot": row}},
                "models": {"model": {"old_blake3": "a" * 64, "new_blake3": "b" * 64}},
                "expressions": {},
                "native_graphs": {
                    "current.dot": {
                        "source_sha256": old_sha,
                        "migrated_sha256": new_sha,
                    }
                },
            }
            self.assertTrue(
                model_identity.accepts_graph(
                    root, "current.dot", old_sha, new_sha, context
                )
            )
            path.write_text(migrated.replace("power=2", "power=3"))
            row["current_sha256"] = data.digest(path)
            self.assertFalse(
                model_identity.accepts_graph(
                    root, "current.dot", old_sha, data.digest(path), context
                )
            )
            # Updating both replay preimages and their receipt cannot replace
            # the geometry authenticated by the sealed native validation.
            (root / "original.dot").write_text(original.replace("power=2", "power=3"))
            row["original"].update(data.file_record(root / "original.dot"))
            self.assertFalse(
                model_identity.accepts_graph(
                    root,
                    "current.dot",
                    row["original"]["sha256"],
                    row["current_sha256"],
                    context,
                )
            )

    def test_replaced_five_loop_rows_need_an_exact_replayable_migration_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            old, new = "a" * 64, "b" * 64
            original = (
                f'digraph {{\n  graph [model_fingerprint="{old}", label="P7", '
                'master_id="L5_f_p1"];\n  a -> b [power=2]; }\n'
            )
            sealed = "5L/masters/P7/graph.dot"
            (root / "original.dot").write_text(original)
            migrated = original.replace(old, new)
            row = {
                "original": {"path": "original.dot", **data.file_record(root / "original.dot")},
                "current_sha256": hashlib.sha256(migrated.encode()).hexdigest(),
                "model_source_sha256": "model",
            }
            receipt = root / model_identity.RECEIPT
            receipt.parent.mkdir(parents=True)
            receipt.write_text("sealed\n")
            context = {
                "receipt": {"graphs": {sealed: row}},
                "models": {"model": {"old_blake3": old, "new_blake3": new}},
                "expressions": {},
                "native_graphs": {sealed: {
                    "source_sha256": row["original"]["sha256"],
                    "migrated_sha256": row["current_sha256"],
                }},
            }
            self.assertEqual(model_identity.superseded_five_loop(root, context), set())
            five = root / "5L"
            (five / "masters/P1").mkdir(parents=True)
            (five / "provenance").mkdir()
            graph = five / "masters/P1/graph.dot"
            graph.write_text("digraph successor {}\n")
            (five / "graphs").mkdir()
            family_graph = five / "graphs/f.dot"
            family_graph.write_bytes(graph.read_bytes())
            data.write_json(root / "manifest.json", {"loop_packs": [
                {"loop_count": 5, "manifest": "5L/manifest.json"}]})
            publication = {"terminal_definitions_sha256": "c" * 64, "terminal_count": 1,
                           "graph_model_fingerprint": new}
            data.write_json(five / "provenance/current-publication.json", publication)
            data.write_json(five / "manifest.json", {"families": [
                {"sha256": "f", "graph": "graphs/f.dot"}], "masters": [{
                "master_id": "L5_f_p1", "name": "P1", "powers": [1],
                "files": {"graph.dot": {"path": "masters/P1/graph.dot",
                                        "sha256": data.digest(graph)}}}]})
            record = {
                "schema": model_identity.FIVE_LOOP_SCHEMA,
                "identity_receipt": model_identity.reference(root, model_identity.RECEIPT),
                "identity_proof_sha256": model_identity.PROOF_SHA256,
                "superseded": {sealed: {"kind": "master", "master_id": "L5_f_p1", "name": "P7",
                                        "original": row["original"],
                                        "current_sha256": row["current_sha256"]}},
                "successor": {"publication": publication, "families": [{
                    "family_sha256": "f", "path": "5L/graphs/f.dot",
                    "sha256": data.digest(family_graph), "previous": None}], "masters": [{
                    "master_id": "L5_f_p1", "name": "P1", "powers": [1],
                    "path": "5L/masters/P1/graph.dot", "sha256": data.digest(graph),
                    "change": "renumbered", "previous": sealed, "previous_name": "P7"}]},
                "removed": [],
            }
            path = root / model_identity.FIVE_LOOP_MIGRATION
            path.parent.mkdir(parents=True)
            data.write_json(path, record)
            self.assertEqual(model_identity.superseded_five_loop(root, context), {sealed})
            for change in (
                lambda r: r["superseded"][sealed].update(current_sha256="0" * 64),
                lambda r: r["superseded"][sealed].update(name="P8"),
                lambda r: r["successor"]["masters"][0].update(change="new", previous=None,
                                                              previous_name=None),
                lambda r: r["successor"]["masters"][0].update(sha256="0" * 64),
                lambda r: r["successor"]["publication"].update(terminal_count=2),
                lambda r: r["identity_receipt"].update(sha256="0" * 64),
            ):
                broken = copy.deepcopy(record)
                change(broken)
                data.write_json(path, broken)
                with self.assertRaises(ValueError):
                    model_identity.superseded_five_loop(root, context)
            data.write_json(path, record)
            # The family graph is the stage-rule representative's graph, even when
            # the record is re-hashed consistently.
            family_graph.write_text("digraph other {}\n")
            rehashed = copy.deepcopy(record)
            rehashed["successor"]["families"][0]["sha256"] = data.digest(family_graph)
            data.write_json(path, rehashed)
            with self.assertRaisesRegex(ValueError, "representative"):
                model_identity.superseded_five_loop(root, context)
            family_graph.write_bytes(graph.read_bytes())
            data.write_json(path, record)
            self.assertEqual(model_identity.superseded_five_loop(root, context), {sealed})
            # The preserved original remains the sealed preimage.
            (root / "original.dot").write_text(original.replace("power=2", "power=3"))
            with self.assertRaises(ValueError):
                model_identity.superseded_five_loop(root, context)


if __name__ == "__main__":
    unittest.main()
