import contextlib
import copy
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

    def provenance_fixture(self):
        directory = self.base / "evidence"
        directory.mkdir()
        path = directory / "vakint-external-data-v0.0.0-cache-build-evidence.tar.gz"
        path.write_bytes(b"source evidence fixture; never a runtime cache")
        asset = {
            "archive": path.name,
            "archive_sha256": data.digest(path),
            "archive_bytes": path.stat().st_size,
        }
        manifest = data.read_json(self.root / "manifest.json")
        manifest["provenance_assets"] = [asset]
        data.write_json(self.root / "manifest.json", manifest)
        return directory, path, manifest

    def test_optional_source_evidence_is_verified_copied_and_checksummed(self):
        directory, evidence, source = self.provenance_fixture()
        output = self.base / "release"
        with patch.object(data, "ROOT", self.root), contextlib.redirect_stdout(io.StringIO()):
            data.pack(output, directory)
        copied = output / evidence.name
        self.assertEqual(copied.read_bytes(), evidence.read_bytes())
        self.assertEqual(
            data.read_json(output / "manifest.json")["provenance_assets"],
            source["provenance_assets"],
        )
        self.assertIn(f"{data.digest(copied)}  {evidence.name}\n", (output / "SHA256SUMS").read_text())
        self.assertEqual(data.read_json(self.root / "manifest.json"), source)

    def test_absent_optional_assets_preserve_legacy_release_bytes(self):
        empty = self.base / "empty-evidence"
        empty.mkdir()
        outputs = [self.base / "legacy", self.base / "optional-empty"]
        with patch.object(data, "ROOT", self.root), contextlib.redirect_stdout(io.StringIO()):
            data.pack(outputs[0])
            data.pack(outputs[1], empty)
        self.assertEqual(
            {p.name: p.read_bytes() for p in outputs[0].iterdir()},
            {p.name: p.read_bytes() for p in outputs[1].iterdir()},
        )
        self.assertEqual(len(list(outputs[0].iterdir())), 7)
        self.assertNotIn("provenance_assets", data.read_json(outputs[0] / "manifest.json"))

    def test_runtime_only_keeps_exact_runtime_bytes_without_source_evidence(self):
        directory, evidence, source = self.provenance_fixture()
        full, runtime = self.base / "full", self.base / "runtime"
        with patch.object(data, "ROOT", self.root), contextlib.redirect_stdout(io.StringIO()):
            data.pack(full, directory)
            evidence.unlink()  # A fresh CI checkout has metadata, not this asset.
            with patch.object(data, "checked_provenance_assets", side_effect=AssertionError("runtime mode accessed external evidence")):
                data.pack(runtime, runtime_only=True)
            with self.assertRaisesRegex(ValueError, "--provenance-assets is required"):
                data.pack(self.base / "still-strict-full")
        manifest = data.read_json(runtime / "manifest.json")
        self.assertEqual((runtime / "manifest.json").read_bytes(), (full / "manifest.json").read_bytes())
        self.assertEqual(manifest["provenance_assets"], source["provenance_assets"])
        for pack in manifest["loop_packs"]:
            self.assertEqual((runtime / pack["archive"]).read_bytes(), (full / pack["archive"]).read_bytes())
        marker = data.read_json(runtime / data.RUNTIME_ONLY_MARKER)
        self.assertIs(marker["publishable"], False)
        self.assertEqual(marker["omitted_provenance_assets"], source["provenance_assets"])
        self.assertEqual(marker["source_manifest_sha256"], data.digest(self.root / "manifest.json"))
        names = {pack["archive"] for pack in manifest["loop_packs"]}
        self.assertEqual({p.name for p in runtime.iterdir()}, names | {"manifest.json", "SHA256SUMS", data.RUNTIME_ONLY_MARKER})
        checksums = (runtime / "SHA256SUMS").read_text()
        self.assertIn(f"{data.digest(runtime / data.RUNTIME_ONLY_MARKER)}  {data.RUNTIME_ONLY_MARKER}\n", checksums)
        self.assertNotIn(evidence.name, checksums)
        self.assertEqual(data.read_json(self.root / "manifest.json"), source)

    def test_runtime_only_requires_fresh_output_and_cannot_silently_become_full(self):
        directory, _, _ = self.provenance_fixture()
        output = self.base / "runtime"
        with patch.object(data, "ROOT", self.root), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, "mutually exclusive"):
                data.pack(output, directory, runtime_only=True)
            self.assertFalse(output.exists())
            data.pack(output, runtime_only=True)
            before = {p.name: p.read_bytes() for p in output.iterdir()}
            with self.assertRaisesRegex(ValueError, "must be empty"):
                data.pack(output, runtime_only=True)
            with self.assertRaisesRegex(ValueError, "use a new output directory"):
                data.pack(output, directory)
        self.assertEqual({p.name: p.read_bytes() for p in output.iterdir()}, before)

    def test_runtime_only_cli_is_explicit_and_deterministic_without_declared_assets(self):
        outputs = [self.base / "runtime-first", self.base / "runtime-second"]
        with patch.object(data, "ROOT", self.root), contextlib.redirect_stdout(io.StringIO()):
            for output in outputs:
                with patch.object(sys, "argv", ["data.py", "pack", "--runtime-only", "--output", str(output)]):
                    data.main()
        self.assertEqual(
            {p.name: p.read_bytes() for p in outputs[0].iterdir()},
            {p.name: p.read_bytes() for p in outputs[1].iterdir()},
        )
        self.assertEqual(data.read_json(outputs[0] / data.RUNTIME_ONLY_MARKER)["omitted_provenance_assets"], [])
        with (
            patch.object(sys, "argv", ["data.py", "pack", "--runtime-only", "--provenance-assets", str(self.base), "--output", str(self.base / "conflict")]),
            contextlib.redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit) as error,
        ):
            data.main()
        self.assertEqual(error.exception.code, 2)

    def test_generated_loop_archive_size_is_checked_before_hash_and_manifest(self):
        # A small explicit test ceiling exercises the same strict boundary
        # without creating a two-gigabyte test file.
        output = self.base / "oversized-release"
        with (
            patch.object(data, "ROOT", self.root),
            patch.object(data, "RELEASE_ASSET_BYTES_LIMIT", 1),
            patch.object(data, "digest", wraps=data.digest) as digest,
            contextlib.redirect_stdout(io.StringIO()),
            self.assertRaisesRegex(ValueError, "generated release archive"),
        ):
            data.pack(output)
        self.assertFalse((output / "manifest.json").exists())
        self.assertFalse((output / "SHA256SUMS").exists())
        self.assertTrue((output / "vakint-external-data-v0.0.0-1L.tar.gz").is_file())
        self.assertTrue(all(output not in call.args[0].parents for call in digest.call_args_list))

    def test_source_evidence_metadata_rejects_unsafe_names_sizes_and_identities(self):
        _, _, manifest = self.provenance_fixture()
        valid = manifest["provenance_assets"][0]
        invalid = [
            {**valid, "archive": name}
            for name in (
                "../evidence.tar.gz", "/evidence.tar.gz", "evidence.tar.gz",
                "vakint-external-data-v0.0.1-evidence.tar.gz",
                "vakint-external-data-v0.0.0-sub/evidence.tar.gz",
                "vakint-external-data-v0.0.0-1L.tar.gz",
                "vakint-external-data-v0.0.0-evidence\\name.tar.gz",
            )
        ] + [
            {**valid, "archive_bytes": value}
            for value in (0, -1, True, "42", 2_000_000_000)
        ] + [
            {**valid, "archive_sha256": "x" * 64},
            {**valid, "archive_sha256": "A" * 64},
            {**valid, "unexpected": "not part of the static contract"},
        ]
        for asset in invalid:
            with self.subTest(asset=asset), self.assertRaises(ValueError):
                data.provenance_assets({**manifest, "provenance_assets": [asset]})
        for assets in (None, {}, [valid, valid]):
            with self.subTest(assets=assets), self.assertRaises(ValueError):
                data.provenance_assets({**manifest, "provenance_assets": assets})

    def test_source_evidence_inventory_and_contents_fail_before_packing(self):
        directory, path, manifest = self.provenance_fixture()
        with self.assertRaisesRegex(ValueError, "required"):
            data.checked_provenance_assets(None, manifest)
        extra = directory / "unexpected.txt"
        extra.write_text("undeclared")
        with self.assertRaisesRegex(ValueError, "inventory"):
            data.checked_provenance_assets(directory, manifest)
        extra.unlink()
        original = path.read_bytes()
        path.write_bytes(b"corrupt")
        with (
            patch.object(data, "digest") as digest,
            self.assertRaisesRegex(ValueError, "checksum/size"),
        ):
            data.checked_provenance_assets(directory, manifest)
        digest.assert_not_called()
        path.write_bytes(b"x" * len(original))
        with self.assertRaisesRegex(ValueError, "checksum/size"):
            data.checked_provenance_assets(directory, manifest)
        path.unlink()
        with self.assertRaisesRegex(ValueError, "inventory"):
            data.checked_provenance_assets(directory, manifest)
        target = self.base / "original"
        target.write_bytes(original)
        path.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "escapes"):
            data.checked_provenance_assets(directory, manifest)
        path.unlink()
        path.mkdir()
        with self.assertRaisesRegex(ValueError, "checksum/size"):
            data.checked_provenance_assets(directory, manifest)
        with patch.object(data, "ROOT", self.root), self.assertRaises(ValueError):
            data.pack(self.base / "not-created", directory)
        self.assertFalse((self.base / "not-created").exists())

    def test_version_change_cannot_leave_static_evidence_on_the_old_version(self):
        self.provenance_fixture()
        before = (self.root / "manifest.json").read_bytes()
        with patch.object(data, "ROOT", self.root), self.assertRaisesRegex(ValueError, "version-bound"):
            data.set_version("v0.0.1")
        self.assertEqual((self.root / "manifest.json").read_bytes(), before)

    def test_packing_rejects_an_evidence_destination_symlink(self):
        directory, evidence, _ = self.provenance_fixture()
        output = self.base / "release"
        output.mkdir()
        (output / evidence.name).symlink_to(evidence)
        with (
            patch.object(data, "ROOT", self.root),
            contextlib.redirect_stdout(io.StringIO()),
            self.assertRaisesRegex(ValueError, "escapes"),
        ):
            data.pack(output, directory)

    def test_evidence_changes_during_packing_do_not_gain_a_new_identity(self):
        directory, _, _ = self.provenance_fixture()
        copy_verified = data.copy_verified

        def changed_copy(source, destination):
            source.write_bytes(b"changed after preflight")
            copy_verified(source, destination)

        with (
            patch.object(data, "ROOT", self.root),
            patch.object(data, "copy_verified", side_effect=changed_copy),
            contextlib.redirect_stdout(io.StringIO()),
            self.assertRaisesRegex(ValueError, "changed while packing"),
        ):
            data.pack(self.base / "release", directory)

    def test_version_update_preserves_all_scientific_payloads_and_current_five_loop(self):
        before = {
            p.relative_to(self.root).as_posix(): p.read_bytes()
            for p in self.root.rglob("*") if p.is_file()
        }
        with patch.object(data, "ROOT", self.root), contextlib.redirect_stdout(io.StringIO()):
            changed = data.set_version("v0.1.2")
            data.validate(self.root)
        self.assertEqual(changed["version"], "v0.1.2")
        for pack in changed["loop_packs"]:
            self.assertEqual(pack["archive"], f"vakint-external-data-v0.1.2-{pack['loop_count']}L.tar.gz")
            old = json.loads(before[pack["manifest"]])
            new = data.read_json(self.root / pack["manifest"])
            old["version"] = "v0.1.2"
            self.assertEqual(new, old)
        for name, payload in before.items():
            if not name.endswith("manifest.json"):
                self.assertEqual((self.root / name).read_bytes(), payload)
        with patch.object(data, "ROOT", self.root):
            for version in ("latest", "v0.01.2", "v0.1.2/../5L", "0.1.2"):
                with self.subTest(version=version), self.assertRaises(ValueError):
                    data.set_version(version)

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
        original = data.read_json(data.ROOT / "provenance/original-root/manifest.json")
        master = next(
            m for m in original["masters"] if m["loop_count"] == 4 and m["name"] == "P5"
        )
        self.assertNotIn(0, master["symbolic_powers"])
        self.assertEqual(master["significant_digits"], 50)

    def producer_fixture(self):
        """Small payloads exercise generation, not native numerical correctness."""
        family = data.digest(self.root / "1L/payload.txt")
        identity = f"L1_{family}_p1"
        directory = self.root / "1L/masters/P1"
        data.write_json(directory / "numerical.json", [[-1, "1"], [0, "2.5"], [1, "3"]])
        data.write_json(
            directory / "symbolic.json", [[-1, "1"], [0, "symbolica::zeta(2)"], [1, "3"]]
        )
        (directory / "graph.dot").write_text("digraph fixture {}\n")
        graphs = self.root / "1L/graphs"
        graphs.mkdir()
        (graphs / f"{family}.dot").write_text("digraph fixture {}\n")
        master = dict(
            master_id=identity, loop_count=1, name="P1", alias="fixture",
            family_sha256=family, powers=[1], status="accepted", significant_digits=50,
            epsilon_range=[-1, 0], symbolic_powers=[-1], directory="1L/masters/P1",
            files={
                name: dict(path=f"1L/masters/P1/{name}", sha256=data.digest(directory / name))
                for name in ("numerical.json", "symbolic.json", "graph.dot")
            },
        )
        original = dict(
            masters=[master], families=[dict(sha256=family, fingerprint="fixture", loop_momenta=["k1"])],
            dimension="4-2*epsilon", normalization="FMFTandMATAD",
            rustred_revision="fixture", vakint_reference_revision="fixture",
        )
        data.write_json(self.root / "provenance/original-root/manifest.json", original)
        data.write_json(self.root / "provenance/migration.json", dict(files=[]))
        data.write_json(
            self.root / "provenance/coefficient-supplement.json",
            dict(schema="vakint.external-data.coefficient-supplement.v1", provenance={}, masters=[
                dict(master_id=identity, coefficients=[
                    dict(epsilon_power=1, symbolic=True, numerical=True, significant_digits=70)
                ])
            ]),
        )
        for loops in range(1, 5):
            base = self.root / f"{loops}L"
            (base / "ibps").mkdir()
            rules = base / "ibps/rules.rrbin"
            rules.write_bytes(f"native fixture {loops}".encode())
            (base / "cache/bindings").mkdir(parents=True)
            bundle = base / "cache/bundle.rrindex"
            bundle.write_bytes(bytes.fromhex(data.digest(rules)))
            data.write_json(base / "cache.json", dict(
                RustRed_revision="fixture", files_sha256={"bundle.rrindex": data.digest(bundle)},
                preparation_report=dict(status="complete", failure=None,
                    total_roots=data.PRIMER_ROOTS[loops], completed_roots=data.PRIMER_ROOTS[loops],
                    newly_stored_intermediates=0, capture_metadata_exhausted_roots=0),
            ))
        data.write_json(self.root / "5L/ibps/application.json", dict(metadata=dict(authority="fixture")))
        update = dict(schema=data.PRODUCER_SCHEMA, provenance=dict(source="fixture"), masters={
            identity: dict(coefficients=[
                dict(epsilon_power=0, symbolic=True, numerical=True, significant_digits=200)
            ])
        })
        return identity, update

    def generate_fixture(self, update):
        data.write_json(self.root / "provenance/producer-update.json", update)
        with (
            patch.object(data, "ROOT", self.root),
            patch.object(data, "generate_graphs", return_value={}),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            data.generate("v0.0.1")

    def test_producer_updates_preserve_extra_orders_identity_and_payloads(self):
        identity, update = self.producer_fixture()
        payload = self.root / "1L/masters/P1/numerical.json"
        payload_before = payload.read_bytes()
        original = (self.root / "provenance/original-root/manifest.json").read_bytes()
        supplement = (self.root / "provenance/coefficient-supplement.json").read_bytes()
        self.generate_fixture(update)
        manifest = data.read_json(self.root / "1L/manifest.json")
        master = manifest["masters"][0]
        self.assertEqual(master["master_id"], identity)
        self.assertEqual(master["powers"], [1])
        self.assertEqual(master["available_epsilon_powers"], [-1, 0, 1])
        self.assertEqual(master["symbolic_powers"], [-1, 0, 1])
        self.assertEqual(
            [c["significant_digits"] for c in master["coefficients"]], [50, 200, 70]
        )
        self.assertEqual(data.read_json(self.root / "1L/producer-update.json"), update)
        self.assertEqual(payload.read_bytes(), payload_before)
        self.assertEqual((self.root / "provenance/original-root/manifest.json").read_bytes(), original)
        self.assertEqual((self.root / "provenance/coefficient-supplement.json").read_bytes(), supplement)
        with contextlib.redirect_stdout(io.StringIO()):
            data.validate(self.root)
        first = (self.root / "1L/manifest.json").read_bytes()
        self.generate_fixture(update)
        self.assertEqual((self.root / "1L/manifest.json").read_bytes(), first)

    def test_producer_rejects_invalid_or_duplicate_capabilities_and_unknown_keys(self):
        identity, baseline = self.producer_fixture()
        invalid = []
        for field, value in [("epsilon_power", True), ("symbolic", 1),
                             ("significant_digits", 0), ("significant_digits", True)]:
            update = copy.deepcopy(baseline)
            update["masters"][identity]["coefficients"][0][field] = value
            invalid.append(update)
        duplicate = copy.deepcopy(baseline)
        duplicate["masters"][identity]["coefficients"] *= 2
        invalid.append(duplicate)
        unknown = copy.deepcopy(baseline)
        unknown["masters"]["unknown"] = unknown["masters"].pop(identity)
        invalid.append(unknown)
        outside = copy.deepcopy(baseline)
        outside["masters"][identity]["coefficients"][0]["epsilon_power"] = 1
        invalid.append(outside)
        for update in invalid:
            with self.subTest(update=update), self.assertRaises(ValueError):
                self.generate_fixture(update)

    def test_producer_rejects_missing_payload_hidden_formula_and_wrong_file_binding(self):
        identity, baseline = self.producer_fixture()
        symbolic = self.root / "1L/masters/P1/symbolic.json"
        data.write_json(symbolic, [[-1, "1"], [1, "3"]])
        with self.assertRaisesRegex(ValueError, "no symbolic payload"):
            self.generate_fixture(baseline)
        data.write_json(symbolic, [[-1, "1"], [0, "symbolica::zeta(2)"], [1, "3"]])
        hidden = copy.deepcopy(baseline)
        hidden["masters"][identity]["coefficients"][0]["symbolic"] = False
        with self.assertRaisesRegex(ValueError, "discard a symbolic expression"):
            self.generate_fixture(hidden)
        wrong = copy.deepcopy(baseline)
        wrong["masters"][identity]["files"] = {
            "symbolic.json": dict(path="masters/P1/symbolic.json", sha256="0" * 64)
        }
        with self.assertRaisesRegex(ValueError, "file binding"):
            self.generate_fixture(wrong)

    def test_producer_receipt_detects_checksum_valid_stale_capabilities(self):
        identity, update = self.producer_fixture()
        self.generate_fixture(update)
        loop_path = self.root / "1L/manifest.json"
        loop = data.read_json(loop_path)
        next(c for c in loop["masters"][0]["coefficients"] if c["epsilon_power"] == 0)[
            "significant_digits"
        ] = 199
        data.write_json(loop_path, loop)
        root = data.read_json(self.root / "manifest.json")
        root["loop_packs"][0]["manifest_sha256"] = data.digest(loop_path)
        data.write_json(self.root / "manifest.json", root)
        with self.assertRaisesRegex(ValueError, "producer capabilities disagree"):
            data.validate(self.root)

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
        self.assertGreaterEqual(len(preserved), 192)
        for entry in preserved:
            self.assertEqual(data.digest(data.ROOT / entry["path"]), entry["sha256"])


if __name__ == "__main__":
    unittest.main()
