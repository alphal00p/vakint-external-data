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
        ]
        (self.directory / "SHA256SUMS").write_text(
            "".join(f"{self.digest(path)}  {path.name}\n" for path in sorted(paths))
        )

    def invoke(self, existing=None, dirty=False):
        calls = []

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
