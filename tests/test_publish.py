import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

SPEC = importlib.util.spec_from_file_location(
    "publish", Path(__file__).resolve().parents[1] / "tools/publish.py"
)
publish = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publish)


class PublicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="vakint-publish-tests-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        self.directory = self.base / "release"
        self.directory.mkdir()
        self.source = {
            "schema": "vakint.external-data.v1",
            "version": "v0.1.1",
            "loop_packs": [
                {
                    "loop_count": loop,
                    "manifest": f"{loop}L/manifest.json",
                    "manifest_sha256": str(loop) * 64,
                    "archive": f"vakint-external-data-v0.1.1-{loop}L.tar.gz",
                    "archive_sha256": None,
                    "archive_bytes": None,
                }
                for loop in range(1, 6)
            ],
        }
        five_loop_manifest = self.root / "5L/manifest.json"
        five_loop_manifest.parent.mkdir()
        five_loop_manifest.write_text(json.dumps({"cache": {"available": False}}))
        self.source["loop_packs"][4]["manifest_sha256"] = self.digest(five_loop_manifest)
        self.manifest = copy.deepcopy(self.source)
        for pack in self.manifest["loop_packs"]:
            archive = self.directory / pack["archive"]
            archive.write_bytes(f"archive fixture {pack['loop_count']}".encode())
            pack["archive_sha256"] = self.digest(archive)
            pack["archive_bytes"] = archive.stat().st_size
        (self.root / "manifest.json").write_text(json.dumps(self.source))
        self.write_manifest_and_checksums()

    @staticmethod
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def write_manifest_and_checksums(self):
        (self.directory / "manifest.json").write_text(json.dumps(self.manifest))
        paths = [self.directory / "manifest.json"] + [
            self.directory / pack["archive"] for pack in self.manifest["loop_packs"]
        ] + [
            self.directory / asset["archive"]
            for asset in self.manifest.get("provenance_assets", [])
        ]
        (self.directory / "SHA256SUMS").write_text(
            "".join(f"{self.digest(path)}  {path.name}\n" for path in sorted(paths))
        )

    def invoke(self, existing=None, dirty=False, calls=None):
        calls = [] if calls is None else calls

        def run(*arguments):
            if arguments == ("git", "status", "--porcelain"):
                return " M manifest.json" if dirty else ""
            self.assertEqual(arguments, ("git", "rev-parse", "HEAD"))
            return "a" * 40

        with (
            patch.object(publish, "ROOT", self.root),
            patch.object(publish, "run", side_effect=run),
            patch.object(publish, "release", return_value=existing),
            patch.object(publish, "query", return_value=None),
            patch.object(publish, "gh", side_effect=lambda *args: calls.append(args)),
            patch.object(sys, "argv", ["publish.py", str(self.directory)]),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            publish.main()
        return calls

    def add_source_evidence(self):
        path = self.directory / "vakint-external-data-v0.1.1-cache-build-evidence.tar.gz"
        path.write_bytes(b"immutable source evidence")
        asset = {"archive": path.name, "archive_sha256": self.digest(path), "archive_bytes": path.stat().st_size}
        self.source["provenance_assets"] = [asset]
        self.manifest["provenance_assets"] = copy.deepcopy(self.source["provenance_assets"])
        (self.root / "manifest.json").write_text(json.dumps(self.source))
        self.write_manifest_and_checksums()
        return path

    def test_optional_evidence_is_uploaded_immutably_before_alias_manifest(self):
        evidence = self.add_source_evidence()
        calls = self.invoke()
        immutable_upload = next(call for call in calls if call[:3] == ("release", "upload", "v0.1.1"))
        self.assertIn(str(evidence), immutable_upload)
        published = calls.index(("release", "edit", "v0.1.1", "--draft=false", "--latest"))
        alias_assets = next(i for i, call in enumerate(calls) if call[:3] == ("release", "upload", "data-latest") and str(evidence) in call)
        alias_manifest = next(i for i, call in enumerate(calls) if call[:3] == ("release", "upload", "data-latest") and str(self.directory / "manifest.json") in call)
        self.assertLess(calls.index(immutable_upload), published)
        self.assertLess(published, alias_assets)
        self.assertLess(alias_assets, alias_manifest)

    def test_runtime_only_marker_rejects_even_complete_assets_before_any_mutation(self):
        self.add_source_evidence()
        marker = self.directory / publish.data.RUNTIME_ONLY_MARKER
        marker.write_text(json.dumps({"schema": "vakint.runtime-only-pack.v1", "publishable": False}))
        calls = []
        with self.assertRaisesRegex(RuntimeError, "runtime-only validation packs are not publishable"):
            self.invoke(calls=calls)
        self.assertEqual(calls, [])

    def test_light_budget_is_rechecked_before_asset_hashes_or_publication(self):
        calls = []
        with (
            patch.object(
                publish.data, "validate_release_cache_budget",
                side_effect=ValueError("official five-loop LIGHT cache exceeds release budget"),
            ) as budget,
            patch.object(publish.hashlib, "file_digest") as digest,
            self.assertRaisesRegex(RuntimeError, "LIGHT cache"),
        ):
            self.invoke(calls=calls)
        budget.assert_called_once_with(self.root, self.manifest)
        digest.assert_not_called()
        self.assertEqual(calls, [])

    def test_removing_runtime_marker_does_not_make_missing_evidence_publishable(self):
        evidence = self.add_source_evidence()
        evidence.unlink()
        marker = self.directory / publish.data.RUNTIME_ONLY_MARKER
        marker.write_text("{}")
        for marked in (True, False):
            if not marked:
                marker.unlink()
            calls = []
            with self.subTest(marked=marked), self.assertRaisesRegex(RuntimeError, "not publishable|not a regular file"):
                self.invoke(calls=calls)
            self.assertEqual(calls, [])

    def test_all_loop_archive_sizes_are_checked_before_hashing_or_mutation(self):
        valid = copy.deepcopy(self.manifest)
        for value in (0, -1, True, "42", 1.5, 2_000_000_000, 2_000_000_001):
            self.manifest = copy.deepcopy(valid)
            # Use the final archive to prove earlier archives are not hashed.
            self.manifest["loop_packs"][-1]["archive_bytes"] = value
            (self.directory / "manifest.json").write_text(json.dumps(self.manifest))
            calls = []
            with (
                self.subTest(value=value),
                patch.object(publish.hashlib, "file_digest") as digest,
                self.assertRaisesRegex(RuntimeError, "positive integers smaller than 2 GB"),
            ):
                self.invoke(calls=calls)
            digest.assert_not_called()
            self.assertEqual(calls, [])

    def test_static_evidence_must_match_committed_metadata_before_any_mutation(self):
        self.add_source_evidence()
        self.manifest["provenance_assets"][0]["archive_sha256"] = "f" * 64
        self.write_manifest_and_checksums()
        calls = []
        with self.assertRaisesRegex(RuntimeError, "committed source manifest"):
            self.invoke(calls=calls)
        self.assertEqual(calls, [])

    def test_corrupt_missing_or_symlink_evidence_is_rejected_before_any_mutation(self):
        path = self.add_source_evidence()
        payload = path.read_bytes()
        for kind in ("corrupt", "missing", "symlink"):
            with self.subTest(kind=kind):
                if path.exists() or path.is_symlink():
                    path.unlink()
                if kind == "corrupt":
                    path.write_bytes(b"different payload")
                elif kind == "symlink":
                    target = self.base / "evidence-original"
                    target.write_bytes(payload)
                    path.symlink_to(target)
                calls = []
                with self.assertRaisesRegex(RuntimeError, "regular file|archive differs"):
                    self.invoke(calls=calls)
                self.assertEqual(calls, [])

    def test_optional_evidence_requires_safe_names_strict_size_and_checksum_inventory(self):
        self.add_source_evidence()
        valid = copy.deepcopy(self.manifest)
        for update in (
            {"archive": "../escape.tar.gz"},
            {"archive": "vakint-external-data-v9.9.9-evidence.tar.gz"},
            {"archive_bytes": 2_000_000_000},
            {"archive_bytes": True},
            {"archive_sha256": "not a hash"},
        ):
            self.manifest = copy.deepcopy(valid)
            self.manifest["provenance_assets"][0].update(update)
            self.source = copy.deepcopy(self.manifest)
            for pack in self.source["loop_packs"]:
                pack.update(archive_sha256=None, archive_bytes=None)
            (self.root / "manifest.json").write_text(json.dumps(self.source))
            (self.directory / "manifest.json").write_text(json.dumps(self.manifest))
            calls = []
            with self.subTest(update=update), self.assertRaises(RuntimeError):
                self.invoke(calls=calls)
            self.assertEqual(calls, [])
        self.manifest = valid
        self.source = copy.deepcopy(valid)
        for pack in self.source["loop_packs"]:
            pack.update(archive_sha256=None, archive_bytes=None)
        (self.root / "manifest.json").write_text(json.dumps(self.source))
        self.write_manifest_and_checksums()
        checksums = self.directory / "SHA256SUMS"
        checksums.write_text("".join(line for line in checksums.read_text().splitlines(keepends=True) if "evidence" not in line))
        calls = []
        with self.assertRaisesRegex(RuntimeError, "SHA256SUMS"):
            self.invoke(calls=calls)
        self.assertEqual(calls, [])

    def test_valid_release_is_published_before_latest_manifest_changes(self):
        calls = self.invoke()
        immutable = calls.index(
            ("release", "edit", "v0.1.1", "--draft=false", "--latest")
        )
        alias_uploads = [
            index
            for index, call in enumerate(calls)
            if call[:3] == ("release", "upload", "data-latest")
        ]
        self.assertTrue(all(index > immutable for index in alias_uploads))
        self.assertEqual(
            calls[alias_uploads[-1]],
            (
                "release",
                "upload",
                "data-latest",
                str(self.directory / "manifest.json"),
                "--clobber",
            ),
        )

    def test_source_identity_allows_only_generated_archive_hashes_and_sizes(self):
        cases = [
            lambda manifest: manifest.update(schema="unsupported.schema"),
            lambda manifest: manifest["loop_packs"][0].update(
                archive="different.tar.gz"
            ),
            lambda manifest: manifest["loop_packs"][0].update(manifest="1L/other.json"),
            lambda manifest: manifest["loop_packs"].append(manifest["loop_packs"][0]),
        ]
        for mutate in cases:
            manifest = copy.deepcopy(self.manifest)
            mutate(manifest)
            with (
                self.subTest(manifest=manifest),
                self.assertRaisesRegex(RuntimeError, "committed source manifest"),
            ):
                publish.checked_assets(self.directory, manifest, self.source)

    def test_checksum_inventory_rejects_stale_missing_extra_and_duplicate_entries(self):
        path = self.directory / "SHA256SUMS"
        correct = path.read_text()
        for value in (
            "0" * 64 + correct[64:],
            "".join(correct.splitlines(keepends=True)[1:]),
            correct + "0" * 64 + "  unexpected.txt\n",
            correct + correct.splitlines(keepends=True)[0],
        ):
            path.write_text(value)
            with (
                self.subTest(value=value),
                self.assertRaisesRegex(RuntimeError, "SHA256SUMS"),
            ):
                self.invoke()

    def test_archive_corruption_is_rejected_even_with_recomputed_checksums(self):
        (self.directory / self.manifest["loop_packs"][0]["archive"]).write_bytes(b"bad")
        self.write_manifest_and_checksums()
        with self.assertRaisesRegex(RuntimeError, "archive differs"):
            self.invoke()

    def test_source_must_be_clean_and_immutable_releases_cannot_be_overwritten(self):
        with self.assertRaisesRegex(RuntimeError, "commit the validated source"):
            self.invoke(dirty=True)
        with self.assertRaisesRegex(RuntimeError, "already published"):
            self.invoke(existing={"isDraft": False, "tagName": "v0.1.1"})

    def test_existing_lightweight_and_annotated_tags_must_resolve_to_source_head(self):
        commit = {"type": "commit", "sha": "a" * 40}
        annotated = {"type": "tag", "sha": "b" * 40}
        for responses in (
            [{"object": commit}],
            [{"object": annotated}, {"object": commit}],
        ):
            with (
                self.subTest(responses=responses),
                patch.object(publish, "query", side_effect=responses) as query,
            ):
                publish.check_release_target("v0.1.1", "a" * 40, None)
                self.assertEqual(query.call_count, len(responses))
        for target in (
            {"type": "commit", "sha": "c" * 40},
            {"type": "tree", "sha": "a" * 40},
        ):
            with (
                self.subTest(target=target),
                patch.object(publish, "query", return_value={"object": target}),
                self.assertRaisesRegex(RuntimeError, "immutable release tag"),
            ):
                publish.check_release_target("v0.1.1", "a" * 40, None)

    def test_uncreated_draft_tag_resolves_its_target_and_rejects_a_different_commit(
        self,
    ):
        draft = {"isDraft": True, "targetCommitish": "main"}
        for commit in ("a" * 40, "b" * 40):
            with (
                self.subTest(commit=commit),
                patch.object(publish, "query", side_effect=[None, {"sha": commit}]),
            ):
                if commit == "a" * 40:
                    publish.check_release_target("v0.1.1", "a" * 40, draft)
                else:
                    with self.assertRaisesRegex(RuntimeError, "release draft"):
                        publish.check_release_target("v0.1.1", "a" * 40, draft)

    def test_broken_and_cyclic_annotated_tags_are_rejected(self):
        annotated = {"object": {"type": "tag", "sha": "b" * 40}}
        for responses in ([annotated, None], [annotated, annotated]):
            with (
                self.subTest(responses=responses),
                patch.object(publish, "query", side_effect=responses),
                self.assertRaisesRegex(RuntimeError, "immutable release tag"),
            ):
                publish.check_release_target("v0.1.1", "a" * 40, None)


if __name__ == "__main__":
    unittest.main()
