"""Official LIGHT publication policy, independently of Native codec limits."""

import contextlib
import copy
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import data
import saved_cache


class ReleaseCacheBudgetTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="vakint-light-cache-budget-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        self.directory = self.root / "5L"
        self.directory.mkdir()
        self.loop = {"cache": {"available": False}}
        self.manifest = {
            "schema": data.ROOT_SCHEMA,
            "version": "v0.0.0",
            "loop_packs": [
                {
                    "loop_count": count,
                    "manifest": f"{count}L/manifest.json",
                    "manifest_sha256": str(count) * 64,
                    "archive": f"vakint-external-data-v0.0.0-{count}L.tar.gz",
                    "archive_sha256": None,
                    "archive_bytes": None,
                }
                for count in range(1, 6)
            ],
        }
        self.write_loop()

    def write_loop(self):
        path = self.directory / "manifest.json"
        data.write_json(path, self.loop)
        self.manifest["loop_packs"][4]["manifest_sha256"] = data.digest(path)
        data.write_json(self.root / "manifest.json", self.manifest)

    def prepared_cache(self):
        path = self.directory / "cache/prepared.rrcache.gz"
        path.parent.mkdir()
        path.write_bytes(b"opaque compressed-cache fixture, not a Native payload")
        self.loop["cache"] = {"available": True, "path": "cache/prepared.rrcache.gz"}
        self.write_loop()
        return path

    @contextlib.contextmanager
    def compressed_size(self, path, size):
        """Exercise byte boundaries without allocating a large payload."""
        original = Path.stat

        def status(candidate, *args, **kwargs):
            result = original(candidate, *args, **kwargs)
            if candidate == path:
                fields = list(result)
                fields[6] = size
                return os.stat_result(fields)
            return result

        with patch.object(Path, "stat", status):
            yield

    def test_no_five_loop_cache_does_not_inspect_or_limit_lower_loop_caches(self):
        # Lower-loop directories need not even be opened by this 5L policy.
        self.assertEqual(
            data.validate_release_cache_budget(self.root, self.manifest), 0
        )

    def test_prepared_cache_uses_decimal_compressed_boundary(self):
        path = self.prepared_cache()
        self.assertGreater(saved_cache.MAX_COMPRESSED, 95_000_000)
        self.assertEqual(saved_cache.MAX_DECODED, 1024 * 1024 * 1024)
        for size in (95_000_000, 95_000_001):
            with self.subTest(size=size), self.compressed_size(path, size):
                if size == 95_000_000:
                    self.assertEqual(
                        data.validate_release_cache_budget(self.root, self.manifest),
                        size,
                    )
                else:
                    with self.assertRaisesRegex(ValueError, "95000001.*95000000"):
                        data.validate_release_cache_budget(self.root, self.manifest)

    def test_prepared_and_selected_parts_share_one_aggregate_budget(self):
        path = self.prepared_cache()
        # The part identities themselves are checked by runtime_cache_assets.
        # Here only their already-authenticated compressed byte count is varied.
        with (
            self.compressed_size(path, 40_000_000),
            patch.object(
                data,
                "runtime_cache_assets",
                return_value=[{"archive_bytes": 55_000_000}],
            ),
        ):
            self.assertEqual(
                data.validate_release_cache_budget(self.root, self.manifest), 95_000_000
            )
        with (
            self.compressed_size(path, 40_000_000),
            patch.object(
                data,
                "runtime_cache_assets",
                return_value=[{"archive_bytes": 55_000_001}],
            ),
            self.assertRaisesRegex(ValueError, "95000001.*95000000"),
        ):
            data.validate_release_cache_budget(self.root, self.manifest)

    def test_full_release_rejects_before_output_or_asset_copy(self):
        path = self.prepared_cache()
        output = self.base / "release"
        with (
            patch.object(data, "ROOT", self.root),
            patch.object(data, "validate", return_value=copy.deepcopy(self.manifest)),
            patch.object(data, "checked_provenance_assets") as provenance,
            patch.object(data, "checked_runtime_cache_assets") as runtime,
            self.compressed_size(path, 95_000_001),
            self.assertRaisesRegex(ValueError, "LIGHT cache"),
        ):
            data.pack(output)
        self.assertFalse(output.exists())
        provenance.assert_not_called()
        runtime.assert_not_called()

    def test_nonpublishable_runtime_pack_does_not_apply_release_budget(self):
        for count in range(1, 5):
            directory = self.root / f"{count}L"
            directory.mkdir()
            (directory / "payload.txt").write_text("tiny opaque runtime fixture")
        output = self.base / "runtime"
        with (
            patch.object(data, "ROOT", self.root),
            patch.object(data, "validate", return_value=copy.deepcopy(self.manifest)),
            patch.object(data, "validate_release_cache_budget") as budget,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            data.pack(output, runtime_only=True)
        budget.assert_not_called()
        self.assertFalse(
            data.read_json(output / data.RUNTIME_ONLY_MARKER)["publishable"]
        )

    def test_policy_authenticates_manifest_and_regular_cache_path(self):
        path = self.prepared_cache()
        self.manifest["loop_packs"][4]["manifest_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "manifest checksum"):
            data.validate_release_cache_budget(self.root, self.manifest)
        self.write_loop()
        path.unlink()
        path.mkdir()
        with self.assertRaisesRegex(ValueError, "regular file"):
            data.validate_release_cache_budget(self.root, self.manifest)


if __name__ == "__main__":
    unittest.main()
