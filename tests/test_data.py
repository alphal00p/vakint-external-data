import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "data", Path(__file__).resolve().parents[1] / "tools/data.py"
)
data = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(data)


class PortableDataTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="vakint-data-tests-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        packs = []
        for loops in range(1, 6):
            directory = self.root / f"{loops}L"
            directory.mkdir()
            payload = directory / "payload.txt"
            payload.write_text(f"immutable payload for {loops} loops\n")
            data.write_json(
                directory / "manifest.json",
                {
                    "schema": data.LOOP_SCHEMA,
                    "version": "v0.0.0",
                    "loop_count": loops,
                    "files": {"payload.txt": data.file_record(payload)},
                    "masters": [],
                    "cache": {"available": False},
                },
            )
            packs.append(
                {
                    "loop_count": loops,
                    "manifest": f"{loops}L/manifest.json",
                    "manifest_sha256": data.digest(directory / "manifest.json"),
                    "archive": f"vakint-external-data-v0.0.0-{loops}L.tar.gz",
                    "archive_sha256": None,
                    "archive_bytes": None,
                }
            )
        data.write_json(
            self.root / "manifest.json",
            {"schema": data.ROOT_SCHEMA, "version": "v0.0.0", "loop_packs": packs},
        )

    def test_corrupt_and_unlisted_payloads_are_rejected(self):
        with contextlib.redirect_stdout(io.StringIO()):
            data.validate(self.root)
        payload = self.root / "1L/payload.txt"
        payload.write_text("corrupt")
        with self.assertRaisesRegex(ValueError, "checksum/size mismatch"):
            data.validate(self.root)
        (self.root / "1L/extra.txt").write_text("not listed")
        with self.assertRaisesRegex(ValueError, "inventory differs"):
            data.validate(self.root)

    def test_unsafe_paths_and_symlink_directories_are_rejected(self):
        for value in ("../escape", "/absolute", "1L/../escape", "./entry", "1L\\entry"):
            with self.assertRaisesRegex(ValueError, "unsafe"):
                data.checked_path(self.root, value)
        (self.root / "1L/alias").symlink_to(self.root / "2L", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            data.validate(self.root)

    def test_deterministic_disjoint_archives(self):
        import tarfile

        first, second = self.base / "first", self.base / "second"
        with (
            patch.object(data, "ROOT", self.root),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            data.pack(first)
            # Metadata changes must not alter deterministic release bytes.
            (self.root / "1L/payload.txt").chmod(0o600)
            data.pack(second)
        self.assertEqual(
            {p.name: data.digest(p) for p in first.iterdir()},
            {p.name: data.digest(p) for p in second.iterdir()},
        )
        manifest = json.loads((first / "manifest.json").read_text())
        for pack in manifest["loop_packs"]:
            archive = first / pack["archive"]
            self.assertEqual(pack["archive_sha256"], data.digest(archive))
            with tarfile.open(archive) as tar:
                self.assertTrue(
                    all(m.name.split("/")[0] == f"{pack['loop_count']}L" for m in tar)
                )
        self.assertTrue(
            all(
                p["archive_sha256"] is None
                for p in data.read_json(self.root / "manifest.json")["loop_packs"]
            )
        )

    def test_generated_five_loop_graphs_have_exact_slot_incidence(self):
        momenta, parents, witnesses = data.five_loop_definitions()
        self.assertEqual(len(momenta), 15)
        self.assertEqual(len(parents), 4)
        self.assertEqual(len(witnesses), 67)
        for witness in witnesses:
            for source, target, sign in zip(
                witness["source_slots"], witness["target_slots"], witness["signs"]
            ):
                transported = [
                    sum(momenta[source][i] * witness["routing"][i][j] for i in range(5))
                    for j in range(5)
                ]
                self.assertEqual(
                    transported, [sign * coefficient for coefficient in momenta[target]]
                )

    def test_archived_numeric_fallback_is_not_an_exact_formula(self):
        manifest = data.read_json(data.ROOT / "4L/manifest.json")
        master = next(m for m in manifest["masters"] if m["name"] == "P5")
        coefficient = next(c for c in master["coefficients"] if c["epsilon_power"] == 0)
        self.assertFalse(coefficient["symbolic"])
        self.assertTrue(coefficient["numerical"])
        self.assertEqual(coefficient["significant_digits"], 50)

    def test_supplemented_orders_have_explicit_capabilities_and_preserved_sources(self):
        supplement = data.read_json(
            data.ROOT / "provenance/coefficient-supplement.json"
        )
        lower = [
            m
            for m in supplement["masters"]
            if m["master_id"].startswith(("L2_", "L3_"))
        ]
        self.assertEqual(len(lower), 22)
        self.assertEqual(sum(len(m["coefficients"]) for m in lower), 25)
        four_loop = [
            m for m in supplement["masters"] if m["master_id"].startswith("L4_")
        ]
        self.assertEqual(len(four_loop), 20)
        self.assertEqual(sum(len(m["coefficients"]) for m in four_loop), 24)
        masters = {
            master["master_id"]: master
            for loops in (2, 3, 4)
            for master in data.read_json(data.ROOT / f"{loops}L/manifest.json")[
                "masters"
            ]
        }
        for entry in supplement["masters"]:
            actual = {
                c["epsilon_power"]: c
                for c in masters[entry["master_id"]]["coefficients"]
            }
            for expected in entry["coefficients"]:
                self.assertEqual(actual[expected["epsilon_power"]], expected)
        preserved = [
            entry
            for entry in data.read_json(data.ROOT / "provenance/migration.json")[
                "files"
            ]
            if entry["path"].startswith("provenance/original-coefficients/")
        ]
        self.assertEqual(len(preserved), 192)
        for entry in preserved:
            self.assertEqual(data.digest(data.ROOT / entry["path"]), entry["sha256"])


if __name__ == "__main__":
    unittest.main()
