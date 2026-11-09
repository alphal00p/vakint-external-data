import json
import shutil
import sys
import tempfile
import unittest
from unittest import mock
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


def library(directory, schema="rustred.p-owner-library.v1", scope=(1, 1)):
    """A small p library directory as `rustred p-package` writes it (library.json + one payload)."""
    a, b = scope
    data.write_json(directory / "library.json", {"schema": schema, "scope": [a, b],
                                                 "identity": f"p-library:scope={a}-{b}:P_TEST=1"})
    (directory / "families").mkdir()
    (directory / "families/P1L.rrbin").write_bytes(b"family" * 1000)
    return directory


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
        report = p_integral_area.stage(self.base / "export", self.root)
        self.assertGreater(report.cache_bytes, 0)
        self.assertGreater(report.bytes, report.cache_bytes)
        after = data.read_json(self.root / "manifest.json")
        self.assertEqual({key: value for key, value in after.items() if key != "p_integral"}, before)
        with self.assertRaisesRegex(ValueError, "--replace"):
            p_integral_area.stage(self.base / "export", self.root)
        self.assertEqual(p_integral_area.stage(self.base / "export", self.root, replace=True), report)
        self.assertEqual(p_integral_area.light_bytes(self.root), report.cache_bytes)
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

    def test_the_per_file_rule(self):
        mb = 1_000_000
        cases = [  # ({path: bytes}, the refusal or None)
            ({"a.rrbin": 50 * mb}, None),
            ({"a.rrbin": 50 * mb + 1}, "compress it"),
            ({"a.rrbin.gz": 100 * mb - 1, "b.rrbin.zst": 99 * mb}, None),
            ({"a.rrbin.zst": 100 * mb}, "below 100000000"),
            ({"a.rrbin.part-000": 50 * mb, "a.rrbin.part-001": 50 * mb, "a.rrbin.part-002": 1}, None),
            ({"a.rrbin.part-000": 60 * mb}, "compress it"),
            ({"a.rrbin.part-000": 1, "a.rrbin.part-002": 1}, "without gaps"),
            ({"a.rrbin.part-000": 1, "a.rrbin": 1}, "whole file"),
        ]
        for sizes, refusal in cases:
            with self.subTest(sizes=sizes):
                if refusal is None:
                    p_integral_area.check_file_rule(sizes)
                else:
                    with self.assertRaisesRegex(ValueError, refusal):
                        p_integral_area.check_file_rule(sizes)
        # validate applies it to every file of the area, libraries included
        p_integral_area.stage_library(library(self.base / "package"), self.root)
        with mock.patch.object(p_integral_area, "LARGE_FILE_BYTES", 5000):
            with self.assertRaisesRegex(ValueError, "p-library-1-1/families/P1L.rrbin: 6000 bytes"):
                p_integral_area.validate(self.root)

    def test_the_light_budget_covers_the_cache_files_only(self):
        p_integral_area.stage(self.base / "export", self.root)
        report = p_integral_area.stage_library(library(self.base / "package"), self.root)
        budget = report.cache_bytes
        self.assertGreater(report.bytes - report.cache_bytes, budget)  # the rest exceeds the budget
        with mock.patch.object(p_integral_area, "LIGHT_CACHE_BYTES_LIMIT", budget):
            p_integral_area.validate(self.root)
        with mock.patch.object(p_integral_area, "LIGHT_CACHE_BYTES_LIMIT", budget - 1):
            with self.assertRaisesRegex(ValueError, "light-cache budget"):
                p_integral_area.validate(self.root)

    def test_a_listed_library_is_validated_and_kept_by_cache_staging(self):
        package = library(self.base / "package", scope=(1, 3))
        report = p_integral_area.stage_library(package, self.root)
        package_bytes = sum(path.stat().st_size for path in package.rglob("*") if path.is_file())
        self.assertEqual(report.libraries, [{"directory": "p-library-1-3", "schema": "rustred.p-owner-library.v1",
                                             "scope": [1, 3], "bytes": package_bytes, "supported": True}])
        self.assertEqual(report.notes, [])
        p_integral_area.stage(self.base / "export", self.root)
        self.assertEqual(len(p_integral_area.validate(self.root).libraries), 1)
        payload = self.root / "p_integral/p-library-1-3/families/P1L.rrbin"
        payload.write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "p-library-1-3/families/P1L.rrbin: sha256 or size"):
            p_integral_area.validate(self.root)
        payload.unlink()
        with self.assertRaisesRegex(ValueError, "p-library-1-3/ file inventory differs"):
            p_integral_area.validate(self.root)

    def test_an_unknown_library_schema_is_reported_not_fatal(self):
        package = library(self.base / "package", schema="rustred.p-owner-library.v9")
        report = p_integral_area.stage_library(package, self.root)
        self.assertEqual([library["supported"] for library in report.libraries], [False])
        self.assertRegex(report.notes[0], "p-library-1-1: schema 'rustred.p-owner-library.v9' is not one")

    def test_the_real_area_validates_when_present(self):
        manifest = json.loads((data.ROOT / "manifest.json").read_text())
        if "p_integral" not in manifest and not (data.ROOT / "p_integral").exists():
            self.skipTest("this checkout carries no p_integral area")
        report = p_integral_area.validate(data.ROOT)
        self.assertLessEqual(report.cache_bytes, p_integral_area.LIGHT_CACHE_BYTES_LIMIT)
        self.assertEqual(report.notes, [])


if __name__ == "__main__":
    unittest.main()
