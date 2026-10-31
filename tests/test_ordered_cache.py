import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import data  # noqa: E402
import ordered_cache  # noqa: E402

STAMP = "ab" * 32
ENGINE = "rustred 0.1.0 sources " + "cd" * 32 + " symbolica git-9cd5767"


def description(engine=ENGINE):
    return (
        "schema rustred.ordered-step-cache.v2\n"
        "semantics rustred-ordered-steps-2026-10-31\n"
        f"engine {engine}\n"
        "adapter candidate-program\n"
        "family 0123abcd\n"
        "program " + "ef" * 32 + "\n"
        "variables 1 d\n"
        "unresolved preserve\n"
        "terminals " + "12" * 32 + "\n"
    )


def shard(stamp, stage, support, payload, digest):
    return (
        ordered_cache.SHARD_MAGIC
        + bytes.fromhex(stamp)
        + bytes([ordered_cache.STAGES[stage]])
        + support.to_bytes(2, "little")
        + (0).to_bytes(8, "little")
        + len(payload).to_bytes(8, "little")
        + bytes.fromhex(digest)
        + payload
    )


def write_program(base, label, records=(3, 5)):
    """A structurally valid RustRed cache directory (BLAKE3 values are opaque here)."""
    directory = base / "ordered-cache" / label
    (directory / "shards").mkdir(parents=True)
    lines = []
    total = 0
    for support, count in enumerate(records, start=1):
        digest = f"{support:02x}" * 32
        name = f"shards/integral-s{support:02d}-0000000000000000.{digest[:16]}.rrstep"
        content = shard(STAMP, "integral", support, b"records" * support, digest)
        (directory / name).write_bytes(content)
        total += len(content)
        lines.append(f"shard integral {support} 0000000000000000 {name} {count} {len(content)} {digest}")
    text = description() + f"stamp {STAMP}\n" + "".join(line + "\n" for line in lines) + "end\n"
    (directory / "ordered-step-cache.txt").write_text(text)
    return {
        "label": label,
        "path": f"ordered-cache/{label}",
        "adapter": "candidate-program",
        "stamp": STAMP,
        "content_blake3": "99" * 32,
        "records": sum(records),
        "shards": len(records),
        "bytes": total,
        "engine": ENGINE,
        "description": description(),
    }


def write_export(base, loop_count=4, labels=("4L-four-loop-h", "4L-four-loop-x")):
    directory = base / f"{loop_count}L"
    programs = [write_program(directory, label) for label in labels]
    data.write_json(directory / "ordered-cache.json", {
        "schema": ordered_cache.SCHEMA,
        "loop_count": loop_count,
        "producer": {"vakint_revision": "0" * 40},
        "workload": [{"name": f"{loop_count}L-zero-momentum"}],
        "programs": programs,
    })
    return programs


class OrderedCacheTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="vakint-ordered-cache-tests-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "repo"
        packs = []
        for loops in range(1, 6):
            directory = self.root / f"{loops}L"
            directory.mkdir(parents=True)
            payload = directory / "payload.txt"
            payload.write_text(f"immutable payload for {loops} loops\n")
            data.write_json(directory / "manifest.json", {
                "schema": data.LOOP_SCHEMA,
                "version": "v0.0.0",
                "loop_count": loops,
                "files": {"payload.txt": data.file_record(payload)},
                "masters": [],
                "cache": {"available": False},
            })
            packs.append({
                "loop_count": loops,
                "manifest": f"{loops}L/manifest.json",
                "manifest_sha256": data.digest(directory / "manifest.json"),
                "archive": f"vakint-external-data-v0.0.0-{loops}L.tar.gz",
                "archive_sha256": None,
                "archive_bytes": None,
            })
        data.write_json(self.root / "manifest.json",
                        {"schema": data.ROOT_SCHEMA, "version": "v0.0.0", "loop_packs": packs})
        self.export = self.base / "export"

    def loop(self, count=4):
        return data.read_json(self.root / f"{count}L/manifest.json")

    def test_staged_caches_are_listed_validated_and_bound_to_the_root_manifest(self):
        write_export(self.export)
        staged = ordered_cache.stage(self.export, self.root)
        self.assertEqual(staged["4L"]["programs"], 2)
        loop = self.loop()
        self.assertEqual(loop["ordered_cache"], ordered_cache.SECTION)
        self.assertIn("ordered-cache.json", loop["files"])
        self.assertEqual(ordered_cache.validate(self.root),
                         {"1L": 0, "2L": 0, "3L": 0, "4L": 2, "5L": 0})
        root = data.read_json(self.root / "manifest.json")
        self.assertEqual(root["loop_packs"][3]["manifest_sha256"],
                         data.digest(self.root / "4L/manifest.json"))
        # Restaging replaces the previous caches of that loop count.
        self.export = self.base / "export-2"
        write_export(self.export, labels=("4L-four-loop-h",))
        ordered_cache.stage(self.export, self.root)
        self.assertFalse((self.root / "4L/ordered-cache/4L-four-loop-x").exists())
        self.assertEqual(ordered_cache.validate(self.root)["4L"], 1)

    def staged(self):
        write_export(self.export)
        ordered_cache.stage(self.export, self.root)
        return self.root / "4L"

    def assert_rejected(self):
        with self.assertRaises(ValueError):
            ordered_cache.validate_loop(self.root / "4L", self.loop())

    def test_shard_headers_must_carry_the_manifest_stamp_and_identity(self):
        directory = self.staged()
        path = next((directory / "ordered-cache/4L-four-loop-h/shards").iterdir())
        content = bytearray(path.read_bytes())
        content[20] ^= 1
        path.write_bytes(bytes(content))
        self.assert_rejected()

    def test_metadata_must_agree_with_the_rustred_manifest(self):
        directory = self.staged()
        metadata = data.read_json(directory / "ordered-cache.json")
        metadata["programs"][0]["records"] += 1
        data.write_json(directory / "ordered-cache.json", metadata)
        self.assert_rejected()

    def test_unlisted_or_missing_cache_files_are_rejected(self):
        directory = self.staged()
        loop = self.loop()
        name = next(n for n in loop["files"] if n.endswith(".rrstep"))
        del loop["files"][name]
        with self.assertRaises(ValueError):
            ordered_cache.validate_loop(directory, loop)
        loop = self.loop()
        del loop["ordered_cache"]
        with self.assertRaises(ValueError):
            ordered_cache.validate_loop(directory, loop)

    def test_exports_with_stray_files_or_wrong_loop_counts_are_refused(self):
        write_export(self.export)
        (self.export / "4L/ordered-cache/4L-four-loop-h/shards/extra.rrstep").write_bytes(b"x")
        with self.assertRaises(ValueError):
            ordered_cache.stage(self.export, self.root)
        other = self.base / "other"
        write_export(other, loop_count=3, labels=("4L-four-loop-h",))
        with self.assertRaises(ValueError):
            ordered_cache.stage(other, self.root)

    def test_shards_above_the_git_file_limit_are_refused(self):
        write_export(self.export)
        with patch.object(ordered_cache, "SHARD_FILE_BYTES_LIMIT", 100):
            with self.assertRaises(ValueError):
                ordered_cache.stage(self.export, self.root)

    def test_retired_dfs_caches_are_recorded_and_keep_the_migration_receipt_valid(self):
        directory = self.root / "3L"
        cache = directory / "cache/bindings/x"
        cache.mkdir(parents=True)
        (cache / "cache.rrindex").write_bytes(b"dfs index")
        (directory / "cache.json").write_text("{}\n")
        loop = self.loop(3)
        for name in ("cache/bindings/x/cache.rrindex", "cache.json"):
            loop["files"][name] = data.file_record(directory / name)
        loop["cache"] = {"available": True, "path": "cache", "metadata": "cache.json"}
        loop["provenance"] = {"native_cache_rustred_revision": "f" * 40}
        data.write_json(directory / "manifest.json", loop)
        migration = {"schema": "vakint.external-data.migration.v1", "files": [
            {"source": "3L/" + name, "path": "3L/" + name, **data.file_record(directory / name)}
            for name in ("cache/bindings/x/cache.rrindex", "payload.txt")]}
        data.write_json(self.root / "provenance/migration.json", migration)
        removed = ordered_cache.remove_dfs(self.root, source_commit="0" * 40)
        self.assertEqual(removed, {"3L": 2})
        self.assertFalse((directory / "cache").exists())
        loop = self.loop(3)
        self.assertEqual(loop["cache"], {"available": False})
        self.assertEqual(loop["provenance"], {})
        receipt = data.read_json(self.root / ordered_cache.RETIREMENT_RECEIPT)
        self.assertEqual(receipt["removed_manifest_sections"]["3L"]["cache"]["metadata"], "cache.json")
        retired = ordered_cache.retired_dfs_files(self.root)
        self.assertEqual(set(retired), {"3L/cache/bindings/x/cache.rrindex", "3L/cache.json"})
        with self.assertRaises(ValueError):
            ordered_cache.remove_dfs(self.root, source_commit="0" * 40)
        self.assertEqual(json.loads((self.root / "manifest.json").read_text())["loop_packs"][2]["manifest_sha256"],
                         data.digest(directory / "manifest.json"))


if __name__ == "__main__":
    unittest.main()
