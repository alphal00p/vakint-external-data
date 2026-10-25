"""Opaque, tiny Native-name fixtures; no Native or algebra dependency."""

import copy
import gzip
import hashlib
import io
import json
import os
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import nativepack


class NativePackTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="nativepack-tests-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.source = self.base / "source"
        self.source.mkdir()
        self.namespace = "a" * 64
        self.chunk = f"cache/bindings/{self.namespace}/chunks/{'b' * 64}.rrchunk.gz"
        self.child = f"cache/bindings/{self.namespace}/cache.rrindex"
        self.binding = {
            "artifact_digest": list(range(32)),
            "family_fingerprint": "opaque-family",
            "physical_arity": 15,
            "layer": "saved-application-route-apply-v1",
        }
        self.write("cache/bundle.rrindex", b"opaque bundle index")
        self.write(self.child, b"opaque binding index")
        self.write(self.chunk, b"opaque encoded Native chunk, not a gzip stream")
        self.output = self.base / "parts"
        self.descriptor = self.pack(self.output)

    def write(self, name, value):
        path = self.source / name.removeprefix("cache/")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
        return path

    def pack(self, output, **options):
        return nativepack.pack_parts(
            self.source,
            output,
            binding=self.binding,
            generation=1,
            stored_record_references=37,
            **options,
        )

    def assert_invalid(self, change):
        descriptor = copy.deepcopy(self.descriptor)
        change(descriptor)
        with self.assertRaises(ValueError):
            nativepack.validate_descriptor(descriptor)

    def replacement_archive(self, payload, descriptor=None, kind="chunks"):
        descriptor = copy.deepcopy(
            self.descriptor if descriptor is None else descriptor
        )
        part = next(part for part in descriptor["parts"] if part["kind"] == kind)
        path = self.output / part["archive"]
        path.write_bytes(payload)
        part["archive_bytes"] = len(payload)
        part["archive_sha256"] = hashlib.sha256(payload).hexdigest()
        return descriptor

    @staticmethod
    def canonical_gzip(value):
        raw = io.BytesIO()
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9
        ) as stream:
            stream.write(value)
        return raw.getvalue()

    def malicious_tar(self, mutate):
        part = next(
            part for part in self.descriptor["parts"] if part["kind"] == "chunks"
        )
        raw = io.BytesIO()
        with (
            gzip.GzipFile(
                filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9
            ) as compressed,
            tarfile.open(
                fileobj=compressed, mode="w|", format=tarfile.USTAR_FORMAT
            ) as archive,
        ):
            for name in part["members"]:
                content = self.source.joinpath(name.removeprefix("cache/")).read_bytes()
                info = nativepack._header(name, len(content))
                info, content = mutate(info, content)
                archive.addfile(info, io.BytesIO(content))
        return self.replacement_archive(raw.getvalue())

    def test_tiny_opaque_files_roundtrip_without_native_decoding(self):
        self.assertIs(nativepack.validate_descriptor(self.descriptor), self.descriptor)
        nativepack.verify_archives(self.descriptor, self.output)
        self.assertEqual(self.descriptor["stored_record_references"], 37)
        self.assertEqual(len(self.descriptor["files"]), 3)
        self.assertEqual(
            [part["kind"] for part in self.descriptor["parts"]], ["chunks", "indexes"]
        )
        self.assertEqual(
            set(self.descriptor["parts"][-1]["members"]),
            {"cache/bundle.rrindex", self.child},
        )

    def test_metadata_types_ranges_and_unknown_fields(self):
        for key in ("generation", "stored_record_references", "loop_count"):
            for bad in (True, -1, 1.5, "1", 1 << 64):
                with self.subTest(key=key, value=bad):
                    self.assert_invalid(
                        lambda value, key=key, bad=bad: value.__setitem__(key, bad)
                    )
        for key, bad in (
            ("artifact_digest", [True] * 32),
            ("artifact_digest", [256] * 32),
            ("artifact_digest", [0] * 31),
            ("physical_arity", 0),
            ("physical_arity", True),
            ("family_fingerprint", ""),
            ("layer", ""),
            ("layer", "\ud800"),
        ):
            with self.subTest(key=key, bad=bad):
                self.assert_invalid(
                    lambda value, key=key, bad=bad: value["binding"].__setitem__(
                        key, bad
                    )
                )
        self.assert_invalid(lambda value: value.__setitem__("unknown", None))
        self.assert_invalid(lambda value: value["binding"].__setitem__("unknown", None))
        self.assert_invalid(
            lambda value: value["parts"][0].__setitem__("unknown", None)
        )
        self.assert_invalid(
            lambda value: value["files"][self.chunk].__setitem__("bytes", True)
        )
        self.assert_invalid(
            lambda value: value["files"][self.chunk].__setitem__("sha256", "A" * 64)
        )

    def test_all_supported_loop_counts_and_inclusive_asset_limit(self):
        for loop in range(1, 6):
            descriptor = copy.deepcopy(self.descriptor)
            descriptor["loop_count"] = loop
            descriptor["parts"][0]["archive_bytes"] = nativepack.PART_BYTES_LIMIT
            nativepack.validate_descriptor(descriptor)
        self.assert_invalid(
            lambda value: value["parts"][0].__setitem__(
                "archive_bytes", nativepack.PART_BYTES_LIMIT + 1
            )
        )
        self.assert_invalid(
            lambda value: value["parts"][0].__setitem__("archive_bytes", 0)
        )

    def test_paths_and_global_partition_are_exact(self):
        for path in (
            "/cache/bundle.rrindex",
            "cache/../bundle.rrindex",
            "cache//bundle.rrindex",
            "cache/./bundle.rrindex",
            "cache\\bundle.rrindex",
            "cache/bundle.rrindex/",
            "cache/bundle.rrindex\0",
            "cache/writer.lock",
            "cache/bindings/A" + "a" * 63 + "/cache.rrindex",
        ):
            with self.subTest(path=path):
                self.assert_invalid(
                    lambda value, path=path: value["files"].__setitem__(
                        path, value["files"]["cache/bundle.rrindex"]
                    )
                )
        self.assert_invalid(
            lambda value: value["parts"][0]["members"].append(self.chunk)
        )
        self.assert_invalid(
            lambda value: value["parts"][-1]["members"].append(self.chunk)
        )
        self.assert_invalid(
            lambda value: value["parts"][0].__setitem__("kind", "indexes")
        )
        self.assert_invalid(lambda value: value["parts"].pop())
        self.assert_invalid(
            lambda value: value["parts"].append(copy.deepcopy(value["parts"][-1]))
        )
        self.assert_invalid(lambda value: value["files"].pop(self.child))
        self.assert_invalid(lambda value: value["files"].pop("cache/bundle.rrindex"))
        self.assert_invalid(lambda value: value["parts"][-1]["members"].reverse())
        for name in (
            "../bad.tar.gz",
            "/bad.tar.gz",
            "a/b.tar.gz",
            "bad.zip",
            "a\\b.tar.gz",
        ):
            self.assert_invalid(
                lambda value, name=name: value["parts"][0].__setitem__("archive", name)
            )

    def test_singular_binding_rejects_a_second_namespace_even_with_exact_membership(
        self,
    ):
        descriptor = copy.deepcopy(self.descriptor)
        child = f"cache/bindings/{'c' * 64}/cache.rrindex"
        chunk = f"cache/bindings/{'c' * 64}/chunks/{'d' * 64}.rrchunk.gz"
        descriptor["files"][child] = copy.deepcopy(descriptor["files"][self.child])
        descriptor["files"][chunk] = copy.deepcopy(descriptor["files"][self.chunk])
        for part in descriptor["parts"]:
            part["members"] = sorted(
                part["members"] + [child if part["kind"] == "indexes" else chunk]
            )
        with self.assertRaisesRegex(ValueError, "exactly one binding namespace"):
            nativepack.validate_descriptor(descriptor)
        # An unrelated chunk also fails when the declared indexes stay singular.
        descriptor["files"].pop(child)
        descriptor["parts"][-1]["members"].remove(child)
        with self.assertRaisesRegex(ValueError, "exactly one binding namespace"):
            nativepack.validate_descriptor(descriptor)

    def test_optional_https_url_is_strict_and_offline_verification_ignores_it(self):
        descriptor = copy.deepcopy(self.descriptor)
        descriptor["parts"][0]["url"] = (
            "https://example.invalid/releases/v1/immutable.tar.gz?token=opaque"
        )
        nativepack.verify_archives(descriptor, self.output)
        for url in (
            "http://example.org/a",
            "https://user:secret@example.org/a",
            "https://example.org/a#fragment",
            "https://example.org/a#",
            "https://example.org/a\n",
            "https://example.org/a\x85",
            "https://example.org\\bad/a",
            "https:///a",
            "https://example.org:99999/a",
            5,
        ):
            with self.subTest(url=url):
                self.assert_invalid(
                    lambda value, url=url: value["parts"][0].__setitem__("url", url)
                )

    def test_deterministic_whole_file_archives_and_source_is_unchanged(self):
        before = {
            path.relative_to(self.source).as_posix(): path.read_bytes()
            for path in self.source.rglob("*")
            if path.is_file()
        }
        os.utime(self.source / "bundle.rrindex", (12345678, 12345678))
        os.chmod(self.source / "bundle.rrindex", 0o600)
        other = self.base / "other"
        descriptor = self.pack(other)
        self.assertEqual(descriptor, self.descriptor)
        for part in descriptor["parts"]:
            self.assertEqual(
                (other / part["archive"]).read_bytes(),
                (self.output / part["archive"]).read_bytes(),
            )
            with tarfile.open(other / part["archive"]) as archive:
                self.assertEqual(archive.getnames(), part["members"])
                for member in archive:
                    self.assertTrue(member.isfile())
                    self.assertEqual(
                        (
                            member.mode,
                            member.uid,
                            member.gid,
                            member.mtime,
                            member.uname,
                            member.gname,
                        ),
                        (0o644, 0, 0, 0, "", ""),
                    )
        self.assertEqual(
            before,
            {
                path.relative_to(self.source).as_posix(): path.read_bytes()
                for path in self.source.rglob("*")
                if path.is_file()
            },
        )

    def test_part_planning_includes_tar_headers_padding_and_record_blocks(self):
        self.write(self.chunk, b"a" * 8500)
        second = f"cache/bindings/{self.namespace}/chunks/{'c' * 64}.rrchunk.gz"
        self.write(second, b"b" * 8500)
        descriptor = self.pack(
            self.base / "split", tar_bytes_target=10240, part_bytes_limit=12000
        )
        chunks = [part for part in descriptor["parts"] if part["kind"] == "chunks"]
        self.assertEqual([part["members"] for part in chunks], [[self.chunk], [second]])
        self.assertEqual(
            nativepack._tar_bytes([self.chunk], descriptor["files"]), 10240
        )
        nativepack.verify_archives(descriptor, self.base / "split")

    def test_changed_partition_cannot_reuse_default_names_for_different_bytes(self):
        self.write(self.chunk, b"a" * 8500)
        self.write(
            f"cache/bindings/{self.namespace}/chunks/{'c' * 64}.rrchunk.gz", b"b" * 8500
        )
        split = self.pack(
            self.base / "split", tar_bytes_target=10240, part_bytes_limit=22000
        )
        joined = self.pack(
            self.base / "joined", tar_bytes_target=20480, part_bytes_limit=22000
        )
        self.assertEqual(len(split["parts"]), 3)
        self.assertEqual(len(joined["parts"]), 2)
        split_names = {
            part["archive"] for part in split["parts"] if part["kind"] == "chunks"
        }
        joined_names = {
            part["archive"] for part in joined["parts"] if part["kind"] == "chunks"
        }
        self.assertTrue(split_names.isdisjoint(joined_names))

    def test_source_mutation_or_new_files_refuse_before_atomic_output(self):
        verifier = nativepack.verify_archives
        for kind in ("changed", "added"):
            target = self.base / kind
            with self.subTest(kind=kind):

                def mutate(descriptor, directory, kind=kind):
                    verifier(descriptor, directory)
                    if kind == "changed":
                        self.write(self.chunk, b"changed while packaging")
                    else:
                        self.write(
                            f"cache/bindings/{self.namespace}/chunks/{'d' * 64}.rrchunk.gz",
                            b"new during packing",
                        )

                with (
                    patch.object(nativepack, "verify_archives", side_effect=mutate),
                    self.assertRaisesRegex(ValueError, "source changed"),
                ):
                    self.pack(target)
                self.assertFalse(target.exists())

    def test_indivisible_file_and_separate_index_bound_refuse_without_partial_output(
        self,
    ):
        target = self.base / "refused"
        with self.assertRaisesRegex(ValueError, "indexes cannot fit"):
            self.pack(target, part_bytes_limit=100)
        self.assertFalse(target.exists())
        self.write(self.chunk, b"large" * 3000)
        with self.assertRaisesRegex(ValueError, "indivisible"):
            self.pack(target, tar_bytes_target=10240, part_bytes_limit=12000)
        self.assertFalse(target.exists())
        self.assertTrue((self.source / self.chunk.removeprefix("cache/")).exists())

    def test_actual_compressed_bound_is_enforced_even_if_plan_underestimates(self):
        with (
            patch.object(nativepack, "_gzip_bound", return_value=1),
            self.assertRaisesRegex(ValueError, "compressed part exceeds"),
        ):
            self.pack(self.base / "actual-refused", part_bytes_limit=50)
        self.assertFalse((self.base / "actual-refused").exists())

    def test_reuse_keeps_base_chunk_archive_bytes_and_replaces_only_indexes(self):
        original = copy.deepcopy(self.descriptor)
        original["parts"][0]["url"] = (
            "https://example.invalid/oldrelease/immutable.tar.gz"
        )
        old_chunk = original["parts"][0]
        self.write("cache/bundle.rrindex", b"new opaque bundle index")
        self.write(self.child, b"new opaque binding index")
        new_chunk = f"cache/bindings/{self.namespace}/chunks/{'0' * 64}.rrchunk.gz"
        self.write(new_chunk, b"new chunk sorts before base chunk")
        new_output = self.base / "delta"
        descriptor = self.pack(
            new_output, base_descriptor=original, base_archives=self.output
        )
        self.assertIn(old_chunk, descriptor["parts"])
        self.assertEqual(
            (self.output / old_chunk["archive"]).read_bytes(),
            (new_output / old_chunk["archive"]).read_bytes(),
        )
        indexes = [part for part in descriptor["parts"] if part["kind"] == "indexes"]
        self.assertEqual(len(indexes), 1)
        self.assertNotEqual(indexes[0]["archive"], original["parts"][-1]["archive"])
        self.assertFalse((new_output / original["parts"][-1]["archive"]).exists())
        nativepack.verify_archives(descriptor, new_output)

    def test_reuse_rejects_changed_missing_or_misbound_base_chunks(self):
        self.write(self.chunk, b"changed chunk bytes")
        with self.assertRaisesRegex(ValueError, "reusable chunks differ"):
            self.pack(
                self.base / "bad-reuse",
                base_descriptor=self.descriptor,
                base_archives=self.output,
            )
        original = copy.deepcopy(self.descriptor)
        original["binding"]["family_fingerprint"] = "other"
        with self.assertRaisesRegex(ValueError, "base binding"):
            self.pack(
                self.base / "misbound",
                base_descriptor=original,
                base_archives=self.output,
            )
        with self.assertRaisesRegex(ValueError, "both required"):
            self.pack(self.base / "half", base_descriptor=self.descriptor)

    def test_refuses_symlinks_unknown_source_files_and_nonempty_output(self):
        with self.assertRaisesRegex(ValueError, "empty"):
            self.pack(self.output)
        with self.assertRaisesRegex(ValueError, "outside"):
            self.pack(self.source / "parts")
        lock = self.source / "unexpected.log"
        lock.write_bytes(b"never package unknown files")
        with self.assertRaisesRegex(ValueError, "non-Native"):
            self.pack(self.base / "bad-source")
        lock.unlink()
        target = self.source / "bundle.rrindex"
        target.unlink()
        target.symlink_to(self.source / self.child.removeprefix("cache/"))
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.pack(self.base / "symlink")

    def test_empty_regular_native_writer_locks_are_preserved_and_never_packaged(self):
        paths = [
            self.source / "writer.lock",
            self.source / "bindings" / self.namespace / "writer.lock",
        ]
        for path in paths:
            path.write_bytes(b"")
        before = [
            (path.stat().st_ino, path.stat().st_mode, path.stat().st_mtime_ns)
            for path in paths
        ]
        output = self.base / "with-locks"
        descriptor = self.pack(output)
        self.assertEqual(descriptor, self.descriptor)
        for path, expected in zip(paths, before, strict=True):
            self.assertTrue(path.is_file())
            self.assertEqual(path.read_bytes(), b"")
            self.assertEqual(
                (path.stat().st_ino, path.stat().st_mode, path.stat().st_mtime_ns),
                expected,
            )
        for part in descriptor["parts"]:
            with tarfile.open(output / part["archive"]) as archive:
                self.assertFalse(
                    any(name.endswith("writer.lock") for name in archive.getnames())
                )
        nativepack.verify_archives(descriptor, output)

    def test_nonempty_symlink_and_fifo_native_locks_are_refused(self):
        for relative in ("writer.lock", f"bindings/{self.namespace}/writer.lock"):
            lock = self.source / relative
            for kind in ("nonempty", "symlink", "fifo"):
                with self.subTest(relative=relative, kind=kind):
                    if kind == "nonempty":
                        lock.write_bytes(b"not an ignorable empty lock")
                    elif kind == "symlink":
                        lock.symlink_to(self.source / "bundle.rrindex")
                    else:
                        os.mkfifo(lock)
                    try:
                        with self.assertRaisesRegex(
                            ValueError, "symlink|empty regular file"
                        ):
                            self.pack(self.base / "bad-lock")
                        self.assertTrue(lock.exists())
                    finally:
                        lock.unlink()

    def test_only_exact_native_writer_lock_locations_are_ignored(self):
        lock = self.source / "bindings" / self.namespace / "chunks" / "writer.lock"
        lock.write_bytes(b"")
        with self.assertRaisesRegex(ValueError, "non-Native file path"):
            self.pack(self.base / "unknown-lock")
        self.assertTrue(lock.exists())

    def test_archive_size_sha_and_member_hash_are_independent(self):
        descriptor = copy.deepcopy(self.descriptor)
        descriptor["parts"][0]["archive_bytes"] += 1
        with self.assertRaisesRegex(ValueError, "archive checksum or size"):
            nativepack.verify_archives(descriptor, self.output)
        descriptor = copy.deepcopy(self.descriptor)
        descriptor["files"][self.chunk]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "member checksum"):
            nativepack.verify_archives(descriptor, self.output)

    def test_archive_wrong_size_refuses_before_reading_or_hashing_payload(self):
        descriptor = copy.deepcopy(self.descriptor)
        descriptor["parts"][0]["archive_bytes"] += 1
        with (
            patch.object(
                Path, "open", side_effect=AssertionError("unexpected payload read")
            ),
            self.assertRaisesRegex(ValueError, "archive checksum or size"),
        ):
            nativepack.verify_archives(descriptor, self.output)

    def test_declared_inflated_part_allowance_refuses_before_archive_io(self):
        descriptor = copy.deepcopy(self.descriptor)
        descriptor["files"][self.chunk]["bytes"] = nativepack.U64_MAX
        # Schema integer validity does not make an unbounded container admissible.
        nativepack.validate_descriptor(descriptor)
        with self.assertRaisesRegex(ValueError, "planned tar exceeds"):
            nativepack.verify_archives(descriptor, self.base / "does-not-exist")

    def test_rejects_link_special_path_and_nondeterministic_metadata(self):
        for attribute, value in (
            ("type", tarfile.SYMTYPE),
            ("type", tarfile.LNKTYPE),
            ("type", tarfile.FIFOTYPE),
            ("name", "../outside"),
            ("mtime", 5),
            ("uid", 5),
            ("mode", 0o755),
            ("uname", "user"),
        ):
            with self.subTest(attribute=attribute, value=value):

                def mutate(info, content, attribute=attribute, value=value):
                    setattr(info, attribute, value)
                    return info, content

                descriptor = self.malicious_tar(mutate)
                with self.assertRaisesRegex(ValueError, "USTAR"):
                    nativepack.verify_archives(descriptor, self.output)

    def test_rejects_extra_gzip_member_trailing_bytes_truncation_and_crc(self):
        original_part = self.descriptor["parts"][0]
        original = (self.output / original_part["archive"]).read_bytes()
        for raw in (
            original + gzip.compress(b"hidden", mtime=0),
            original + b"hidden",
            original[:-3],
            original[:-8] + bytes(8),
        ):
            with self.subTest(length=len(raw)):
                descriptor = self.replacement_archive(raw)
                with self.assertRaises(ValueError):
                    nativepack.verify_archives(descriptor, self.output)
        wrong_mtime = bytearray(original)
        wrong_mtime[4] = 1
        with self.assertRaisesRegex(ValueError, "gzip metadata"):
            nativepack.verify_archives(
                self.replacement_archive(wrong_mtime), self.output
            )

    def test_rejects_hidden_tar_members_and_nonzero_padding(self):
        part = self.descriptor["parts"][0]
        raw = gzip.decompress((self.output / part["archive"]).read_bytes())
        content_end = 512 + self.descriptor["files"][self.chunk]["bytes"]
        corrupt = bytearray(raw)
        corrupt[content_end] = 1
        with self.assertRaisesRegex(ValueError, "padding"):
            nativepack.verify_archives(
                self.replacement_archive(self.canonical_gzip(corrupt)), self.output
            )
        corrupt = bytearray(raw)
        corrupt[-1] = 1
        with self.assertRaisesRegex(ValueError, "terminators"):
            nativepack.verify_archives(
                self.replacement_archive(self.canonical_gzip(corrupt)), self.output
            )

    def make_reference(self, descriptor=None, name="snapshot"):
        value = self.descriptor if descriptor is None else descriptor
        path = self.base / "repo" / "5L" / "cache" / f"{name}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        return {
            "loop_count": 5,
            "manifest": f"5L/cache/{name}.json",
            "manifest_bytes": path.stat().st_size,
            "manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    def test_reference_authentication_and_duplicate_json_fields(self):
        row = self.make_reference()
        root = self.base / "repo"
        self.assertEqual(nativepack.validate_reference(root, row), self.descriptor)
        for key, bad in (
            ("manifest", "../snapshot.json"),
            ("manifest", "5L/cache/../snapshot.json"),
            ("manifest_bytes", True),
            ("manifest_bytes", row["manifest_bytes"] + 1),
            ("manifest_bytes", nativepack.U64_MAX),
            ("manifest_sha256", "0" * 64),
            ("loop_count", 4),
        ):
            broken = {**row, key: bad}
            with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                nativepack.validate_reference(root, broken)
        path = root / row["manifest"]
        path.write_text('{"schema":"bad",' + path.read_text()[1:])
        row["manifest_bytes"] = path.stat().st_size
        row["manifest_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            nativepack.validate_reference(root, row)

    def test_public_json_reader_rejects_nested_duplicate_fields_for_cli_inputs(self):
        path = self.base / "input.json"
        for value in (
            '{"layer":"first","layer":"second"}',
            '{"binding":{"layer":"first","layer":"second"}}',
        ):
            path.write_text(value, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate NativePack JSON key"):
                nativepack.read_json(path)
        for value in ("NaN", "Infinity", "-Infinity"):
            path.write_text('{"generation":' + value + "}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non-finite"):
                nativepack.read_json(path)
        path.write_text(json.dumps(self.binding), encoding="utf-8")
        self.assertEqual(nativepack.read_json(path), self.binding)

    def test_reference_and_archive_symlink_ancestors_are_rejected(self):
        row = self.make_reference()
        root = self.base / "repo"
        cache = root / "5L" / "cache"
        cache.rename(root / "5L" / "real")
        cache.symlink_to("real", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            nativepack.validate_reference(root, row)
        part = self.descriptor["parts"][0]
        path = self.output / part["archive"]
        actual = self.base / "actual.tar.gz"
        path.rename(actual)
        path.symlink_to(actual)
        with self.assertRaisesRegex(ValueError, "symlink"):
            nativepack.verify_archives(self.descriptor, self.output)

    def test_flattened_assets_allow_identical_base_reuse_and_reject_conflicts(self):
        first = self.make_reference(name="first")
        second = self.make_reference(name="second")
        manifest = {"runtime_cache_snapshots": [first, second]}
        self.assertEqual(
            nativepack.assets(manifest, self.base / "repo"), self.descriptor["parts"]
        )
        with self.assertRaisesRegex(ValueError, "duplicate.*reference"):
            nativepack.assets(
                {"runtime_cache_snapshots": [first, first]}, self.base / "repo"
            )
        changed = copy.deepcopy(self.descriptor)
        changed["parts"][0]["archive_sha256"] = "0" * 64
        manifest["runtime_cache_snapshots"][1] = self.make_reference(
            changed, name="conflict"
        )
        with self.assertRaisesRegex(ValueError, "conflicting"):
            nativepack.assets(manifest, self.base / "repo")
        self.assertEqual(nativepack.assets({}, self.base), [])


if __name__ == "__main__":
    unittest.main()
