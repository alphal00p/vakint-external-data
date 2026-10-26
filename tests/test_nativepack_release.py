"""Release integration for optional Native snapshots using tiny opaque files.

These fixtures exercise transport metadata, never native reduction or decoding.
"""

import contextlib
import copy
import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import data
import nativepack
import publish
import saved_cache


class NativePackReleaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="vakint-nativepack-release-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        packs = []
        for count in range(1, 6):
            directory = self.root / f"{count}L"
            directory.mkdir()
            (directory / "payload.txt").write_text(f"immutable {count}L payload\n")
            loop = {
                "schema": data.LOOP_SCHEMA,
                "version": "v0.0.0",
                "loop_count": count,
                "files": {},
                "masters": [],
                "cache": {"available": False},
            }
            if count == 5:
                (directory / "ibps").mkdir()
                (directory / "ibps/application.json").write_text(
                    '{"fixture":"no native program"}\n'
                )
                loop.update(
                    dimension="4-2*epsilon",
                    normalization="FMFTandMATAD",
                    families=[
                        {"fingerprint": "fixture-family", "denominators": [{}] * 15}
                    ],
                )
            self.write_loop(count, loop)
            packs.append(
                {
                    "loop_count": count,
                    "manifest": f"{count}L/manifest.json",
                    "manifest_sha256": data.digest(directory / "manifest.json"),
                    "archive": f"vakint-external-data-v0.0.0-{count}L.tar.gz",
                    "archive_sha256": None,
                    "archive_bytes": None,
                }
            )
        self.source = {
            "schema": data.ROOT_SCHEMA,
            "version": "v0.0.0",
            "loop_packs": packs,
        }
        data.write_json(self.root / "manifest.json", self.source)
        self.loop = data.read_json(self.root / "5L/manifest.json")
        self.binding = {
            "artifact_digest": saved_cache.semantic_digest(self.root / "5L", self.loop),
            "family_fingerprint": "fixture-family",
            "physical_arity": 15,
            "layer": "saved-application-route-apply-v1",
        }
        bundle = self.base / "native-source"
        self.native_source = bundle
        binding_directory = bundle / "bindings" / ("a" * 64)
        chunks = binding_directory / "chunks"
        chunks.mkdir(parents=True)
        (bundle / "bundle.rrindex").write_bytes(b"opaque bundle index fixture\n")
        (binding_directory / "cache.rrindex").write_bytes(
            b"opaque binding index fixture\n"
        )
        (chunks / (("b" * 64) + ".rrchunk.gz")).write_bytes(
            b"opaque native chunk fixture\n"
        )
        self.assets_directory = self.base / "runtime-assets"
        self.descriptor = nativepack.pack_parts(
            bundle,
            self.assets_directory,
            binding=self.binding,
            generation=1,
            stored_record_references=3,
        )
        self.descriptor_path = self.root / "5L/cache" / (("c" * 64) + ".json")
        self.write_descriptor(self.descriptor)

    def write_loop(self, count, loop):
        directory = self.root / f"{count}L"
        loop["files"] = {
            path.relative_to(directory).as_posix(): data.file_record(path)
            for path in sorted(directory.rglob("*"))
            if path.is_file() and path != directory / "manifest.json"
        }
        data.write_json(directory / "manifest.json", loop)

    def write_descriptor(self, descriptor):
        data.write_json(self.descriptor_path, descriptor)
        self.source["runtime_cache_snapshots"] = [
            {
                "loop_count": 5,
                "manifest": self.descriptor_path.relative_to(self.root).as_posix(),
                "manifest_sha256": data.digest(self.descriptor_path),
                "manifest_bytes": self.descriptor_path.stat().st_size,
            }
        ]
        self.write_loop(5, self.loop)
        self.source["loop_packs"][4]["manifest_sha256"] = data.digest(
            self.root / "5L/manifest.json"
        )
        data.write_json(self.root / "manifest.json", self.source)

    def build_release(self, name="release", **kwargs):
        output = self.base / name
        with (
            patch.object(data, "ROOT", self.root),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            data.pack(output, **kwargs)
        return output

    def checked_release(self, output, manifest=None):
        manifest = (
            data.read_json(output / "manifest.json") if manifest is None else manifest
        )
        with patch.object(publish, "ROOT", self.root):
            return publish.checked_assets(output, manifest, self.source)

    def test_root_references_authenticate_real_descriptors_and_flatten_parts(self):
        assets = data.runtime_cache_assets(self.root, self.source)
        self.assertEqual(assets, self.descriptor["parts"])
        with contextlib.redirect_stdout(io.StringIO()):
            data.validate(self.root)
        self.assertFalse(
            data.read_json(self.root / "5L/manifest.json")["cache"]["available"]
        )
        self.assertTrue(all(part["archive_bytes"] < 2_000_000_000 for part in assets))

    def test_reference_rejects_changed_descriptor_identity_and_unsafe_paths(self):
        valid = copy.deepcopy(self.source)
        for change in (
            {"manifest_sha256": "0" * 64},
            {"manifest_bytes": self.descriptor_path.stat().st_size + 1},
            {"manifest_bytes": True},
            {"manifest": "../outside.json"},
            {"manifest": "/absolute.json"},
            {"manifest": "5L/cache/../outside.json"},
            {"loop_count": 4},
            {"unexpected": "not part of a reference"},
        ):
            source = copy.deepcopy(valid)
            source["runtime_cache_snapshots"][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                data.runtime_cache_assets(self.root, source)
        self.descriptor_path.write_bytes(self.descriptor_path.read_bytes() + b" ")
        with self.assertRaises(ValueError):
            data.runtime_cache_assets(self.root, valid)

    def test_symlink_descriptor_is_rejected_even_with_matching_bytes(self):
        original = self.base / "descriptor-original.json"
        shutil.copyfile(self.descriptor_path, original)
        self.descriptor_path.unlink()
        self.descriptor_path.symlink_to(original)
        with self.assertRaises(ValueError):
            data.runtime_cache_assets(self.root, self.source)

    def test_reserved_descriptor_basenames_refuse_before_release_output_creation(self):
        for name in ("manifest.json", data.RUNTIME_ONLY_MARKER):
            self.descriptor_path = self.root / "5L/cache" / name
            self.write_descriptor(self.descriptor)
            output = self.base / f"reserved-{name}"
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    data.runtime_cache_assets(self.root, self.source)
                with self.assertRaises(ValueError):
                    self.build_release(
                        output.name, runtime_cache_directory=self.assets_directory
                    )
                self.assertFalse(output.exists())

    def test_snapshot_binding_must_match_live_five_loop_application(self):
        saved_cache.validate_nativepack(self.root / "5L", self.loop, self.descriptor)
        for field, value in (
            ("artifact_digest", [0] * 32),
            ("family_fingerprint", "different-family"),
            ("physical_arity", 14),
            ("physical_arity", True),
            ("layer", "different-layer"),
        ):
            descriptor = copy.deepcopy(self.descriptor)
            descriptor["binding"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                saved_cache.validate_nativepack(self.root / "5L", self.loop, descriptor)
        (self.root / "5L/ibps/application.json").write_text('{"fixture":"changed"}\n')
        with self.assertRaises(ValueError):
            saved_cache.validate_nativepack(
                self.root / "5L", self.loop, self.descriptor
            )

    def test_full_pack_requires_explicit_runtime_archives(self):
        output = self.base / "missing-runtime-assets"
        with (
            patch.object(data, "ROOT", self.root),
            contextlib.redirect_stdout(io.StringIO()),
            self.assertRaises(ValueError),
        ):
            data.pack(output)
        self.assertFalse((output / "manifest.json").exists())

    def test_optional_part_urls_do_not_replace_explicit_local_archives(self):
        descriptor = copy.deepcopy(self.descriptor)
        for part in descriptor["parts"]:
            part["url"] = (
                f"https://example.invalid/releases/download/v0.0.0/{part['archive']}"
            )
        self.write_descriptor(descriptor)
        self.assertEqual(
            data.runtime_cache_assets(self.root, self.source), descriptor["parts"]
        )
        with self.assertRaises(ValueError):
            self.build_release("urls-without-local-assets")
        output = self.build_release(
            "urls-with-local-assets", runtime_cache_directory=self.assets_directory
        )
        self.assertEqual(data.read_json(output / self.descriptor_path.name), descriptor)
        self.checked_release(output)

    def test_full_pack_preserves_source_and_copies_every_authenticated_part(self):
        before = {
            path.relative_to(self.root): path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file()
        }
        output = self.build_release(runtime_cache_directory=self.assets_directory)
        manifest = data.read_json(output / "manifest.json")
        self.assertEqual(
            manifest["runtime_cache_snapshots"], self.source["runtime_cache_snapshots"]
        )
        checksums = (output / "SHA256SUMS").read_text()
        for part in self.descriptor["parts"]:
            name = part["archive"]
            self.assertEqual(
                (output / name).read_bytes(),
                (self.assets_directory / name).read_bytes(),
            )
            self.assertIn(f"{part['archive_sha256']}  {name}\n", checksums)
        self.assertEqual(
            before,
            {
                path.relative_to(self.root): path.read_bytes()
                for path in self.root.rglob("*")
                if path.is_file()
            },
        )
        expected = {pack["archive"] for pack in manifest["loop_packs"]}
        expected.update(part["archive"] for part in self.descriptor["parts"])
        expected.add(self.descriptor_path.name)
        self.assertEqual(
            (output / self.descriptor_path.name).read_bytes(),
            self.descriptor_path.read_bytes(),
        )
        self.assertIn(
            f"{data.digest(self.descriptor_path)}  {self.descriptor_path.name}\n",
            checksums,
        )
        self.assertEqual(
            {Path(path).name for path in self.checked_release(output)}, expected
        )

    def test_full_pack_rejects_missing_extra_corrupt_and_symlink_parts(self):
        part = self.descriptor["parts"][0]
        path = self.assets_directory / part["archive"]
        original = path.read_bytes()
        for kind in ("missing", "extra", "corrupt", "symlink"):
            if path.exists() or path.is_symlink():
                path.unlink()
            path.write_bytes(original)
            extra = self.assets_directory / "unexpected.tar.gz"
            if kind == "missing":
                path.unlink()
            elif kind == "extra":
                extra.write_bytes(b"not declared")
            elif kind == "corrupt":
                path.write_bytes(bytes([original[0] ^ 1]) + original[1:])
            elif kind == "symlink":
                target = self.base / "part-original.tar.gz"
                target.write_bytes(original)
                path.unlink()
                path.symlink_to(target)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.build_release(
                    f"invalid-{kind}", runtime_cache_directory=self.assets_directory
                )
            if extra.exists():
                extra.unlink()

    def test_runtime_only_omits_external_parts_but_keeps_descriptor_and_loop_bytes(
        self,
    ):
        full = self.build_release("full", runtime_cache_directory=self.assets_directory)
        shutil.rmtree(self.assets_directory)
        runtime = self.build_release("runtime", runtime_only=True)
        self.assertEqual(
            (runtime / "manifest.json").read_bytes(),
            (full / "manifest.json").read_bytes(),
        )
        for pack in data.read_json(runtime / "manifest.json")["loop_packs"]:
            self.assertEqual(
                (runtime / pack["archive"]).read_bytes(),
                (full / pack["archive"]).read_bytes(),
            )
        marker = data.read_json(runtime / data.RUNTIME_ONLY_MARKER)
        self.assertIs(marker["publishable"], False)
        self.assertEqual(
            marker["omitted_runtime_cache_assets"], self.descriptor["parts"]
        )
        self.assertEqual(
            (runtime / self.descriptor_path.name).read_bytes(),
            self.descriptor_path.read_bytes(),
        )
        checksums = (runtime / "SHA256SUMS").read_text()
        for part in self.descriptor["parts"]:
            self.assertFalse((runtime / part["archive"]).exists())
            self.assertNotIn(part["archive"], checksums)
        with self.assertRaises(RuntimeError):
            self.checked_release(runtime)
        (runtime / data.RUNTIME_ONLY_MARKER).unlink()
        with self.assertRaises(RuntimeError):
            self.checked_release(runtime)

    def test_publisher_rejects_corrupt_part_even_with_recomputed_checksum_inventory(
        self,
    ):
        output = self.build_release(runtime_cache_directory=self.assets_directory)
        path = output / self.descriptor["parts"][0]["archive"]
        original = path.read_bytes()
        path.write_bytes(bytes([original[0] ^ 1]) + original[1:])
        checksums = output / "SHA256SUMS"
        checksums.write_text(
            "".join(
                f"{data.digest(output / line.split('  ', 1)[1])}  {line.split('  ', 1)[1]}\n"
                for line in checksums.read_text().splitlines()
            )
        )
        with self.assertRaises(RuntimeError):
            self.checked_release(output)

    def test_publisher_requires_each_part_once_in_complete_checksums(self):
        output = self.build_release(runtime_cache_directory=self.assets_directory)
        checksums = output / "SHA256SUMS"
        original = checksums.read_text()
        part_name = self.descriptor["parts"][0]["archive"]
        part_line = next(
            line
            for line in original.splitlines(keepends=True)
            if line.endswith(f"  {part_name}\n")
        )
        for changed in (original.replace(part_line, ""), original + part_line):
            checksums.write_text(changed)
            with (
                self.subTest(checksums=changed),
                self.assertRaisesRegex(RuntimeError, "SHA256SUMS"),
            ):
                self.checked_release(output)

    def test_same_loop_snapshot_selection_rejects_identical_and_distinct_references(
        self,
    ):
        second = self.root / "5L/cache" / (("d" * 64) + ".json")
        data.write_json(second, self.descriptor)
        second_reference = {
            "loop_count": 5,
            "manifest": second.relative_to(self.root).as_posix(),
            "manifest_sha256": data.digest(second),
            "manifest_bytes": second.stat().st_size,
        }
        self.write_loop(5, self.loop)
        self.source["loop_packs"][4]["manifest_sha256"] = data.digest(
            self.root / "5L/manifest.json"
        )
        first_reference = self.source["runtime_cache_snapshots"][0]
        selections = (
            [first_reference, copy.deepcopy(first_reference)],
            [first_reference, second_reference],
            [second_reference, first_reference],
        )
        for index, references in enumerate(selections):
            self.source["runtime_cache_snapshots"] = references
            data.write_json(self.root / "manifest.json", self.source)
            with self.subTest(references=references):
                with self.assertRaisesRegex(
                    ValueError, "multiple selected runtime cache snapshots for 5L"
                ):
                    data.runtime_cache_assets(self.root, self.source)
                output = self.base / f"duplicate-selection-{index}"
                with self.assertRaisesRegex(
                    ValueError, "multiple selected runtime cache snapshots for 5L"
                ):
                    self.build_release(
                        output.name, runtime_cache_directory=self.assets_directory
                    )
                self.assertFalse(output.exists())
        self.assertEqual(nativepack.read_json(second), self.descriptor)
        nativepack.verify_archives(self.descriptor, self.assets_directory)

    def test_publisher_rejects_unlisted_runtime_archive_and_changed_static_reference(
        self,
    ):
        output = self.build_release(runtime_cache_directory=self.assets_directory)
        extra = output / "unlisted-runtime-part.tar.gz"
        extra.write_bytes(b"not declared by any descriptor")
        with self.assertRaises(RuntimeError):
            self.checked_release(output)
        extra.unlink()
        manifest = data.read_json(output / "manifest.json")
        manifest["runtime_cache_snapshots"][0]["manifest_sha256"] = "0" * 64
        with self.assertRaises(RuntimeError):
            self.checked_release(output, manifest)

    def test_optional_snapshot_absence_preserves_legacy_release_inventory(self):
        self.descriptor_path.unlink()
        self.source.pop("runtime_cache_snapshots")
        self.write_loop(5, self.loop)
        self.source["loop_packs"][4]["manifest_sha256"] = data.digest(
            self.root / "5L/manifest.json"
        )
        data.write_json(self.root / "manifest.json", self.source)
        output = self.build_release()
        self.assertEqual(len(list(output.iterdir())), 7)
        self.assertNotIn(
            "runtime_cache_snapshots", data.read_json(output / "manifest.json")
        )
        self.assertEqual(len(self.checked_release(output)), 5)

    def invoke_nativepack_cli(self, output, descriptor):
        binding = self.base / "public-binding.json"
        data.write_json(binding, self.binding)
        arguments = [
            "data.py",
            "pack-nativepack",
            "--source",
            str(self.native_source),
            "--output",
            str(output),
            "--descriptor",
            str(descriptor),
            "--binding",
            str(binding),
            "--generation",
            "2",
            "--stored-record-references",
            "3",
        ]
        with (
            patch.object(sys, "argv", arguments),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            data.main()

    def test_pack_nativepack_cli_preserves_source_and_keeps_descriptor_outside_archives(
        self,
    ):
        import tarfile

        before = {
            path.relative_to(self.native_source): path.read_bytes()
            for path in self.native_source.rglob("*")
            if path.is_file()
        }
        output = self.base / "cli-parts"
        descriptor_path = self.base / "cli-metadata/snapshot.json"
        self.invoke_nativepack_cli(output, descriptor_path)
        descriptor = data.read_json(descriptor_path)
        nativepack.verify_archives(descriptor, output)
        self.assertEqual(descriptor["generation"], 2)
        self.assertEqual(descriptor["binding"], self.binding)
        self.assertEqual(
            {path.name for path in output.iterdir()},
            {part["archive"] for part in descriptor["parts"]},
        )
        for part in descriptor["parts"]:
            with tarfile.open(output / part["archive"]) as archive:
                self.assertEqual(archive.getnames(), part["members"])
                self.assertFalse(
                    any(name.endswith(".json") for name in archive.getnames())
                )
        self.assertEqual(
            before,
            {
                path.relative_to(self.native_source): path.read_bytes()
                for path in self.native_source.rglob("*")
                if path.is_file()
            },
        )

    def test_pack_nativepack_cli_rejects_source_or_archive_descriptor_and_existing_outputs(
        self,
    ):
        before = {
            path.relative_to(self.native_source): path.read_bytes()
            for path in self.native_source.rglob("*")
            if path.is_file()
        }
        existing_descriptor = self.base / "existing-descriptor.json"
        existing_descriptor.write_bytes(b"preserve existing descriptor\n")
        existing_output = self.base / "existing-parts"
        existing_output.mkdir()
        (existing_output / "preserved.txt").write_bytes(b"preserve existing output\n")
        cases = (
            (self.base / "source-desc-parts", self.native_source / "snapshot.json"),
            (self.base / "inside-parts", self.base / "inside-parts/snapshot.json"),
            (self.base / "existing-desc-parts", existing_descriptor),
            (existing_output, self.base / "new-descriptor.json"),
        )
        for output, descriptor in cases:
            with (
                self.subTest(output=output, descriptor=descriptor),
                self.assertRaises(ValueError),
            ):
                self.invoke_nativepack_cli(output, descriptor)
            if output != existing_output:
                self.assertFalse(output.exists())
            if descriptor != existing_descriptor:
                self.assertFalse(descriptor.exists())
        self.assertEqual(
            existing_descriptor.read_bytes(), b"preserve existing descriptor\n"
        )
        self.assertEqual(
            (existing_output / "preserved.txt").read_bytes(),
            b"preserve existing output\n",
        )
        self.assertEqual(
            before,
            {
                path.relative_to(self.native_source): path.read_bytes()
                for path in self.native_source.rglob("*")
                if path.is_file()
            },
        )


if __name__ == "__main__":
    unittest.main()
