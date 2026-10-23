import copy
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import data
import replace_five_loop as refresh


class FiveLoopReplacementTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="vakint-five-loop-replace-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "repo"
        source = data.ROOT
        # Mathematical fixture is an actual retained numerator integral; only the
        # tiny native payload is mocked, since its binary replay is a Rust test.
        existing = data.read_json(source / "5L/manifest.json")
        family = copy.deepcopy(existing["families"][0])
        self.definitions = {
            "families": [family], "masters": [{
                "family_fingerprint": family["fingerprint"],
                "powers": [0, 0, 1, -1, 0, 0, 1, 0, 0, 1, 0, 1, 1, 1, 1]}],
            "source_manifest_blake3": "fixture-manifest", "source_scope_binding": "fixture-scope",
        }
        packs = []
        for loops in range(1, 6):
            directory = self.root / f"{loops}L"
            directory.mkdir(parents=True)
            (directory / "payload.txt").write_text(f"original-{loops}\n")
            data.write_json(directory / "manifest.json", {"files": {}, "cache": {"available": False}})
            packs.append({"loop_count": loops, "manifest": f"{loops}L/manifest.json",
                          "manifest_sha256": data.digest(directory / "manifest.json"),
                          "archive_sha256": None, "archive_bytes": None})
        data.write_json(self.root / "manifest.json", {
            "schema": data.ROOT_SCHEMA, "version": "v0.1.1", "loop_packs": packs})
        (self.root / "provenance").mkdir()
        shutil.copyfile(source / "provenance/five_loop_data.rs", self.root / "provenance/five_loop_data.rs")
        shutil.copyfile(source / "4L/model.json", self.root / "4L/model.json")
        (self.root / "4L/masters/P1").mkdir(parents=True)
        shutil.copyfile(source / "4L/masters/P1/graph.dot", self.root / "4L/masters/P1/graph.dot")
        self.application = self.base / "native"
        self.application.mkdir()
        data.write_json(self.application / "application.json", {
            "schema": "rustred.saved-application.v1", "metadata": {
                "remaining_terminals": 1, "source_manifest_blake3": "fixture-manifest",
                "source_scope_binding": "fixture-scope", "source_generation": 7,
                "authority": "fixture only; native replay is independently tested",
            }})
        (self.application / "terminal-maps.rrbin").write_bytes(b"native-fixture")
        self.definitions_path = self.base / "terminals.json"
        data.write_json(self.definitions_path, self.definitions)

    def stage(self, name="staged"):
        output = self.base / name
        refresh.stage(self.root, self.application, self.definitions_path, output, expected=1)
        return output

    def test_deterministic_graph_has_complete_numerator_and_defining_chords(self):
        before = refresh.lower_snapshot(self.root)
        first, second = self.stage(), self.stage("second")
        self.assertEqual(refresh.inventory(first), refresh.inventory(second))
        graph = (first / "masters/P1/graph.dot").read_text()
        self.assertIn('digraph feynkit', graph)
        self.assertIn('feynkit_name="P1"', graph)
        self.assertIn('label="P1"', graph)
        self.assertIn('master_id="L5_', graph)
        self.assertIn('lmb_id=0', graph)
        self.assertIn('-UFO::mUV^2', graph)
        self.assertIn('common_basis_to_graph_loops=', graph)
        self.assertIn('family_powers="[0, 0, 1, -1,', graph)
        manifest = refresh.validate_stage(first)
        self.assertEqual(manifest["cache"], {"available": False})
        self.assertEqual(manifest["masters"][0]["coefficients"], [])
        self.assertEqual(set(manifest["masters"][0]["files"]), {"graph.dot"})
        self.assertEqual(before, refresh.lower_snapshot(self.root))

    def test_native_key_order_is_deterministic_and_duplicate_rejected(self):
        values = copy.deepcopy(self.definitions)
        second = copy.deepcopy(values["masters"][0])
        second["powers"][3] = 0
        values["masters"].append(second)
        _, first = refresh.terminal_records(values)
        values["masters"].reverse()
        self.assertEqual(first, refresh.terminal_records(values)[1])
        self.assertEqual([r["name"] for r in first], ["P1", "P2"])
        values["masters"].append(second)
        with self.assertRaisesRegex(ValueError, "duplicate native terminal"):
            refresh.terminal_records(values)

    def test_binding_and_mass_mismatch_fail_before_staging(self):
        self.definitions["source_manifest_blake3"] = "another"
        data.write_json(self.definitions_path, self.definitions)
        with self.assertRaisesRegex(ValueError, "different source_manifest"):
            self.stage()
        self.assertFalse((self.base / "staged").exists())
        self.definitions["source_manifest_blake3"] = "fixture-manifest"
        self.definitions["families"][0]["denominators"][0]["constant"] = "0"
        data.write_json(self.definitions_path, self.definitions)
        with self.assertRaisesRegex(ValueError, "denominators differ"):
            self.stage()
        self.assertFalse((self.base / "staged").exists())

    def test_manifest_corruption_and_unexpected_master_values_rejected(self):
        staged = self.stage()
        (staged / "masters/P1/graph.dot").write_text("corrupt")
        with self.assertRaisesRegex(ValueError, "inventory differs"):
            refresh.validate_stage(staged)
        staged = self.stage("other")
        manifest = data.read_json(staged / "manifest.json")
        manifest["masters"][0]["coefficients"] = [{"epsilon_power": 0}]
        data.write_json(staged / "manifest.json", manifest)
        with self.assertRaisesRegex(ValueError, "only a graph"):
            refresh.validate_stage(staged)

    def test_install_preserves_lower_packs_and_moves_old_payload_outside_checkout(self):
        staged = self.stage()
        data.write_json(self.root / "provenance/migration.json", {"files": [
            {"source": "1L/payload.txt", "path": "1L/payload.txt"},
            {"source": "5L/payload.txt", "path": "5L/payload.txt"},
        ]})
        data.write_json(self.root / "provenance/native-graphs/migration.json", {
            "models": [{"path": "4L/model.json"}, {"path": "5L/model.json"}], "graphs": []})
        for relative in ("provenance/five-loop-graphs", "provenance/native-graphs/original/5L"):
            archive = self.root / relative
            archive.mkdir(parents=True)
            (archive / "old.txt").write_text("old")
        before = refresh.lower_snapshot(self.root)
        result = refresh.install(self.root, staged, self.base / "backup")
        self.assertEqual(before, refresh.lower_snapshot(self.root))
        self.assertEqual(result["masters"], 1)
        self.assertFalse((self.root / "5L/payload.txt").exists())
        self.assertTrue((self.base / "backup/5L/payload.txt").exists())
        self.assertFalse((self.root / "provenance/five-loop-graphs").exists())
        self.assertEqual(data.read_json(self.root / "provenance/migration.json")["files"],
                         [{"source": "1L/payload.txt", "path": "1L/payload.txt"}])
        self.assertEqual(data.read_json(self.root / "provenance/native-graphs/migration.json")["models"],
                         [{"path": "4L/model.json"}])
        with patch.object(data, "ROOT", self.root):
            with self.assertRaisesRegex(ValueError, "historical generate would replace"):
                data.generate("v0.1.2")
        with self.assertRaisesRegex(ValueError, "historical graph migration"):
            refresh.five_loop_graphs.generate_five_loop_graphs({}, root=self.root)


if __name__ == "__main__":
    unittest.main()
