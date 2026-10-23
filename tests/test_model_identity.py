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


if __name__ == "__main__":
    unittest.main()
