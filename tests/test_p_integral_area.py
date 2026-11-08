import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import data  # noqa: E402
import ordered_cache  # noqa: E402
import p_integral_area  # noqa: E402

STAMP = "cd" * 32
IDENTITY = "p-library:scope=1-1:P_OWNER_LIBRARY_SEMANTICS=rustred-p-owner-library-2026-11-05"
NAME = "p-library-1-1_p-owner-library-2026-11-05_ordered-step-cache.v3_ordered-steps-2026-10-31"
VERSIONS = {"ordered_step_cache_schema": ordered_cache.RUSTRED_CACHE_SCHEMA,
            "ordered_step_semantics": "rustred-ordered-steps-2026-10-31",
            "ordered_tail_schema": ordered_cache.TAIL_SCHEMA,
            "ordered_tail_semantics": "rustred-ordered-tail-2026-10-31"}


def shard(payload, digest="ee" * 32):
    return (ordered_cache.SHARD_MAGIC + bytes.fromhex(STAMP) + bytes([ordered_cache.STAGES["apply"]])
            + (3).to_bytes(2, "little") + (0).to_bytes(8, "little") + len(payload).to_bytes(8, "little")
            + bytes.fromhex(digest) + payload)


def export(directory):
    """An export as Vakint's export_ordered_caches writes it: one scope-1 program, one shard."""
    program = directory / "p_integral/ordered-cache" / NAME
    (program / "shards").mkdir(parents=True)
    payload = shard(b"records")
    (program / "shards/apply.bin").write_bytes(payload)
    (program / ordered_cache.RUSTRED_MANIFEST).write_text(
        f"schema {ordered_cache.RUSTRED_CACHE_SCHEMA}\nsemantics {VERSIONS['ordered_step_semantics']}\n"
        f"adapter propagator-library\nfamily {IDENTITY}\nvariables 1 d\nunresolved reject\nstamp {STAMP}\n"
        f"shard apply 3 0000000000000000 shards/apply.bin 2 {len(payload)} {'ee' * 32}\nend\n")
    data.write_json(directory / "p_integral/ordered-cache.json", {
        "schema": p_integral_area.METADATA_SCHEMA,
        "producer": {"rustred": VERSIONS},
        "workload": [],
        "programs": [{"label": "p-library-1-1", "scope": [1, 1], "directory": f"ordered-cache/{NAME}",
                      "identity": IDENTITY, "p_versions": {}, "stamp": STAMP,
                      "adapter": "propagator-library", "records": 2, "shards": 1,
                      "bytes": len(payload), "tail_bytes": 0, "complete": True, "trim": None}],
    })


class PIntegralAreaTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="vakint-p-integral-area-tests-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        data.write_json(self.root / "manifest.json", {"schema": "vakint.external-data.v1",
                                                      "version": "v0.2.2", "loop_packs": []})
        export(self.base / "export")

    def test_a_staged_area_validates_and_adds_only_the_root_key(self):
        before = data.read_json(self.root / "manifest.json")
        total = p_integral_area.stage(self.base / "export", self.root)
        self.assertGreater(total, 0)
        after = data.read_json(self.root / "manifest.json")
        self.assertEqual({key: value for key, value in after.items() if key != "p_integral"}, before)
        with self.assertRaisesRegex(ValueError, "--replace"):
            p_integral_area.stage(self.base / "export", self.root)
        self.assertEqual(p_integral_area.stage(self.base / "export", self.root, replace=True), total)
        self.assertEqual(p_integral_area.light_bytes(self.root), total)
        self.assertEqual(p_integral_area.light_bytes(self.base), 0)

    def test_tampered_areas_are_refused(self):
        p_integral_area.stage(self.base / "export", self.root)
        shard_path = self.root / "p_integral/ordered-cache" / NAME / "shards/apply.bin"
        payload = bytearray(shard_path.read_bytes())
        payload[-1] ^= 1
        shard_path.write_bytes(payload)
        with self.assertRaisesRegex(ValueError, "sha256 or size"):
            p_integral_area.validate(self.root)
        shutil.rmtree(self.root / "p_integral")
        with self.assertRaisesRegex(ValueError, "missing"):
            p_integral_area.validate(self.root)

    def test_the_real_area_validates_when_present(self):
        manifest = json.loads((data.ROOT / "manifest.json").read_text())
        if "p_integral" not in manifest and not (data.ROOT / "p_integral").exists():
            self.skipTest("this checkout carries no p_integral area")
        self.assertLessEqual(p_integral_area.validate(data.ROOT), p_integral_area.BYTES_LIMIT)


if __name__ == "__main__":
    unittest.main()
