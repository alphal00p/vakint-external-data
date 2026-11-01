import copy
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import data  # noqa: E402
import ordered_cache  # noqa: E402

STAMP = "ab" * 32
OTHER_STAMP = "ac" * 32
FAMILY = "rustred-integral-family-v2;N3:test;L3"
ADAPTER_OF = {3: "closed-artifact", 4: "candidate-program", 5: "saved-application"}


def description(adapter, schema=ordered_cache.RUSTRED_CACHE_SCHEMA):
    unresolved = "none" if adapter == "closed-artifact" else "preserve"
    return (
        f"schema {schema}\n"
        "semantics rustred-ordered-steps-2026-10-31\n"
        f"adapter {adapter}\n"
        f"family {FAMILY}\n"
        "variables 1 d\n"
        f"unresolved {unresolved}\n"
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


def tail(adapter, payload=b"tail payload", schema=ordered_cache.TAIL_SCHEMA):
    identity = (
        f"schema {schema}\nsemantics rustred-ordered-tail-2026-10-31\n"
        f"adapter {ordered_cache.ADAPTERS[adapter]}\nfamily {json.dumps(FAMILY)}\n"
        'variables ["d"]\nunresolved none\n'
    ).encode()
    return (ordered_cache.TAIL_MAGIC + len(identity).to_bytes(8, "little") + identity
            + len(payload).to_bytes(8, "little") + b"\x11" * 32 + payload)


def write_program(base, label, tables, *, records=(3, 5), stamp=STAMP, with_tail=False,
                  name_stamp=None, schema=ordered_cache.RUSTRED_CACHE_SCHEMA):
    """A structurally valid RustRed v3 cache directory (BLAKE3 values are opaque here)."""
    adapter = ADAPTER_OF[int(label[0])]
    directory = base / f"{label}.{tables[:16]}.{(name_stamp or stamp)[:16]}"
    (directory / "shards").mkdir(parents=True)
    lines = []
    for support, count in enumerate(records, start=1):
        digest = f"{support:02x}" * 32
        name = f"shards/integral-s{support:02d}-0000000000000000.{digest[:16]}.rrstep"
        (directory / name).write_bytes(shard(stamp, "integral", support, b"records" * support, digest))
        size = (directory / name).stat().st_size
        lines.append(f"shard integral {support} 0000000000000000 {name} {count} {size} {digest}")
    text = description(adapter, schema) + f"stamp {stamp}\n" + "".join(line + "\n" for line in lines) + "end\n"
    (directory / ordered_cache.RUSTRED_MANIFEST).write_text(text)
    if with_tail:
        (directory / ordered_cache.TAIL_FILE).write_bytes(tail(adapter))
    return directory


def shards_bytes(directory):
    return sum(path.stat().st_size for path in (directory / "shards").iterdir())


class OrderedCacheTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="vakint-ordered-cache-tests-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.make_repo(self.base / "repo")
        self.cache = self.base / "cache"
        self.cache.mkdir()

    def make_repo(self, root):
        packs = []
        for loops in range(1, 6):
            directory = root / f"{loops}L"
            (directory / "ibps").mkdir(parents=True)
            files = {}
            (directory / "payload.txt").write_text(f"immutable payload for {loops} loops\n")
            files["payload.txt"] = None
            loop = {
                "schema": data.LOOP_SCHEMA,
                "version": "v0.0.0",
                "loop_count": loops,
                "dimension": "4-2*epsilon",
                "normalization": "test",
                "families": [],
                "masters": [],
                "cache": {"available": False},
                "files": files,
            }
            if loops <= 3:
                (directory / "ibps/rules.rrbin").write_bytes(f"rules {loops}".encode())
                files["ibps/rules.rrbin"] = None
            elif loops == 4:
                for name in ("h", "x"):
                    for extension in ordered_cache.FOUR_LOOP_INPUTS:
                        (directory / f"ibps/{name}.{extension}").write_text(f"{name} {extension}")
                        files[f"ibps/{name}.{extension}"] = None
            else:
                (directory / "ibps/application.json").write_text('{"application": 5}\n')
                files["ibps/application.json"] = None
                loop["families"] = [{"name": "tide_five_loop_test", "fingerprint": "fp5"}]
                loop["masters"] = [{"family_sha256": "f" * 64, "powers": [1, 1, -1]}]
            for name in files:
                files[name] = data.file_record(directory / name)
            loop["files"] = dict(sorted(files.items()))
            data.write_json(directory / "manifest.json", loop)
            packs.append({
                "loop_count": loops,
                "manifest": f"{loops}L/manifest.json",
                "manifest_sha256": data.digest(directory / "manifest.json"),
                "archive": f"vakint-external-data-v0.0.0-{loops}L.tar.gz",
                "archive_sha256": None,
                "archive_bytes": None,
            })
        data.write_json(root / "manifest.json",
                        {"schema": data.ROOT_SCHEMA, "version": "v0.0.0", "loop_packs": packs})
        return root

    def loop(self, count, root=None):
        return data.read_json((root or self.root) / f"{count}L/manifest.json")

    def tables(self, count, root=None):
        root = root or self.root
        return ordered_cache.program_rule_tables(root / f"{count}L", self.loop(count, root))

    def program(self, label, **options):
        loops = int(label[0])
        return write_program(self.cache, label, self.tables(loops)[label], **options)

    def assert_rejected(self, count):
        with self.assertRaises(ValueError):
            ordered_cache.validate_loop(self.root / f"{count}L", self.loop(count))

    def test_rule_tables_follow_vakint_identities(self):
        self.assertEqual(self.tables(3), {
            "3L-unit-mass-vacuum-k6": hashlib.sha256(b"rules 3").hexdigest()})
        four = self.tables(4)
        self.assertEqual(set(four), {"4L-four-loop-h", "4L-four-loop-x"})
        expected = hashlib.sha256(b"vakint-ordered-cache-rule-tables-v1\0")
        for extension in ordered_cache.FOUR_LOOP_INPUTS:
            path = f"ibps/h.{extension}"
            for field in (path, self.loop(4)["files"][path]["sha256"]):
                expected.update(len(field).to_bytes(8, "little") + field.encode())
        self.assertEqual(four["4L-four-loop-h"], expected.hexdigest())
        self.assertEqual(list(self.tables(5)), ["5L-tide-five-loop-test"])
        # Every identity field of the saved application enters the five-loop identity.
        loop = self.loop(5)
        before = self.tables(5)["5L-tide-five-loop-test"]
        for change in ("dimension", "normalization", "families", "masters"):
            edited = copy.deepcopy(loop)
            if change == "families":
                edited["families"][0]["fingerprint"] = "fp6"
            elif change == "masters":
                edited["masters"][0]["powers"] = [1, 1, 0]
            else:
                edited[change] += "x"
            self.assertNotEqual(ordered_cache.program_rule_tables(self.root / "5L", edited)
                                ["5L-tide-five-loop-test"], before, change)

    def test_rule_tables_of_this_checkout_equal_the_identities_vakint_reports(self):
        # Prefixes of `rule_tables` in Vakint's ordered-cache statistics (1L-3L, 4L fg and 5L
        # reported by runs on this data; h, bmw and x by the same declared_rule_tables).
        expected = {
            "1L-unit-mass-vacuum-k1": "f8a740e9707e4560",
            "2L-unit-mass-vacuum-k3": "778ab2e6ef9f4934",
            "3L-unit-mass-vacuum-k6": "383b2ebbc1124bef",
            "4L-four-loop-h": "b5cbd317fb5155c5",
            "4L-four-loop-fg": "0b67c3c5a0b19a29",
            "4L-four-loop-bmw": "911209920104145b",
            "4L-four-loop-x": "2f60f1ca938f469b",
            "5L-tide-five-loop-common-basis": "a244b9b4ce8f7228",
        }
        found = {}
        for pack in data.read_json(data.ROOT / "manifest.json")["loop_packs"]:
            path = data.ROOT / pack["manifest"]
            found.update(ordered_cache.program_rule_tables(path.parent, data.read_json(path)))
        self.assertEqual({label: tables[:16] for label, tables in found.items()}, expected)

    def test_cache_directories_are_staged_listed_validated_and_bound_to_the_root_manifest(self):
        self.program("3L-unit-mass-vacuum-k6")
        self.program("4L-four-loop-h")
        self.program("4L-four-loop-x", with_tail=True)
        before = self.loop(1)
        staged = ordered_cache.stage_cache_dir(self.cache, self.root, metadata={
            "producer": {"rustred": {"revision": "0" * 40}},
            "workload": [{"name": "3L-zero", "loop_count": 3}, {"name": "4L-zero", "loop_count": 4}],
        })
        self.assertEqual(set(staged), {"3L", "4L"})
        loop = self.loop(4)
        self.assertEqual(loop["ordered_cache"], ordered_cache.SECTION)
        self.assertEqual(list(loop).index("ordered_cache"), list(loop).index("cache") + 1)
        metadata = data.read_json(self.root / "4L/ordered-cache.json")
        self.assertEqual(metadata["schema"], ordered_cache.SCHEMA)
        self.assertEqual(metadata["workload"], [{"name": "4L-zero", "loop_count": 4}])
        h, x = metadata["programs"]
        self.assertEqual(h["label"], "4L-four-loop-h")
        self.assertEqual(h["directory"], f"ordered-cache/4L-four-loop-h.{h['rule_tables'][:16]}.{STAMP[:16]}")
        self.assertEqual((h["stamp"], h["adapter"], h["records"], h["shards"], h["tail_bytes"]),
                         (STAMP, "candidate-program", 8, 2, 0))
        self.assertTrue(h["complete"])
        self.assertIsNone(h["trim"])
        self.assertEqual(x["tail_bytes"], len(tail("candidate-program")))
        self.assertIn(f"{x['directory']}/{ordered_cache.TAIL_FILE}", loop["files"])
        for name, record in loop["files"].items():
            self.assertEqual(data.file_record(self.root / "4L" / name), record)
        self.assertEqual(ordered_cache.validate(self.root), {"1L": 0, "2L": 0, "3L": 1, "4L": 2, "5L": 0})
        root = data.read_json(self.root / "manifest.json")
        self.assertEqual(root["loop_packs"][3]["manifest_sha256"], data.digest(self.root / "4L/manifest.json"))
        self.assertEqual(self.loop(1), before)
        # Restaging replaces the previous caches of that loop count only.
        shutil.rmtree(self.cache)
        self.cache.mkdir()
        self.program("4L-four-loop-h", stamp=OTHER_STAMP)
        ordered_cache.stage_cache_dir(self.cache, self.root)
        self.assertEqual(ordered_cache.validate(self.root)["4L"], 1)
        self.assertEqual(ordered_cache.validate(self.root)["3L"], 1)
        self.assertEqual(len(list((self.root / "4L/ordered-cache").iterdir())), 1)

    def test_remove_restores_the_pack(self):
        loop_bytes = (self.root / "5L/manifest.json").read_bytes()
        root_bytes = (self.root / "manifest.json").read_bytes()
        self.program("5L-tide-five-loop-test", with_tail=True)
        ordered_cache.stage_cache_dir(self.cache, self.root, link=True)
        self.assertEqual(ordered_cache.validate(self.root)["5L"], 1)
        ordered_cache.remove_loop(self.root, 5)
        self.assertEqual((self.root / "5L/manifest.json").read_bytes(), loop_bytes)
        self.assertEqual((self.root / "manifest.json").read_bytes(), root_bytes)
        self.assertFalse((self.root / "5L/ordered-cache").exists())

    def test_exports_shaped_like_the_packs_stage_identically(self):
        self.program("4L-four-loop-h", with_tail=True)
        ordered_cache.stage_cache_dir(self.cache, self.root, metadata={"producer": {"p": 1}, "workload": []})
        export = self.base / "export"
        (export / "4L").mkdir(parents=True)
        shutil.copytree(self.root / "4L/ordered-cache", export / "4L/ordered-cache")
        shutil.copyfile(self.root / "4L/ordered-cache.json", export / "4L/ordered-cache.json")
        other = self.make_repo(self.base / "other")
        ordered_cache.stage_export(export, other)
        self.assertEqual((other / "4L/manifest.json").read_bytes(), (self.root / "4L/manifest.json").read_bytes())
        # A stray program directory in the export is refused.
        write_program(export / "4L/ordered-cache", "4L-four-loop-x", self.tables(4)["4L-four-loop-x"])
        with self.assertRaises(ValueError):
            ordered_cache.stage_export(export, other)

    def test_directories_must_carry_the_pack_rule_tables_the_stamp_and_a_known_label(self):
        write_program(self.cache, "3L-unit-mass-vacuum-k6", "0" * 64)
        with self.assertRaisesRegex(ValueError, "rule tables"):
            ordered_cache.stage_cache_dir(self.cache, self.root)
        shutil.rmtree(self.cache)
        self.cache.mkdir()
        self.program("3L-unit-mass-vacuum-k6", name_stamp=OTHER_STAMP)
        with self.assertRaisesRegex(ValueError, "stamp"):
            ordered_cache.stage_cache_dir(self.cache, self.root)
        shutil.rmtree(self.cache)
        self.cache.mkdir()
        write_program(self.cache, "4L-four-loop-fg", "1" * 64)
        with self.assertRaisesRegex(ValueError, "loads no program"):
            ordered_cache.stage_cache_dir(self.cache, self.root)

    def test_staged_metadata_must_agree_with_the_pack_and_the_files(self):
        self.program("3L-unit-mass-vacuum-k6")
        ordered_cache.stage_cache_dir(self.cache, self.root)
        directory = self.root / "3L"
        original = data.read_json(directory / "ordered-cache.json")
        for key, value in (("records", 9), ("tail_bytes", 1), ("rule_tables", "1" * 64), ("complete", "yes")):
            metadata = copy.deepcopy(original)
            metadata["programs"][0][key] = value
            data.write_json(directory / "ordered-cache.json", metadata)
            loop = self.loop(3)
            loop["files"]["ordered-cache.json"] = data.file_record(directory / "ordered-cache.json")
            with self.subTest(key=key), self.assertRaises(ValueError):
                ordered_cache.validate_loop(directory, loop)

    def test_shard_headers_inventory_and_rustred_schema_are_checked(self):
        self.program("3L-unit-mass-vacuum-k6")
        ordered_cache.stage_cache_dir(self.cache, self.root)
        program = next((self.root / "3L/ordered-cache").iterdir())
        path = next((program / "shards").iterdir())
        content = path.read_bytes()
        path.write_bytes(content[:20] + bytes([content[20] ^ 1]) + content[21:])
        self.assert_rejected(3)
        path.write_bytes(content)
        ordered_cache.validate_loop(self.root / "3L", self.loop(3))
        (program / "shards/extra.rrstep").write_bytes(b"x")
        self.assert_rejected(3)
        (program / "shards/extra.rrstep").unlink()
        loop = self.loop(3)
        del loop["files"][next(name for name in loop["files"] if name.endswith(".rrstep"))]
        with self.assertRaises(ValueError):
            ordered_cache.validate_loop(self.root / "3L", loop)
        loop = self.loop(3)
        del loop["ordered_cache"]
        with self.assertRaises(ValueError):
            ordered_cache.validate_loop(self.root / "3L", loop)
        shutil.rmtree(self.cache)
        self.cache.mkdir()
        self.program("3L-unit-mass-vacuum-k6", schema="rustred.ordered-step-cache.v2")
        with self.assertRaisesRegex(ValueError, "schema"):
            ordered_cache.stage_cache_dir(self.cache, self.root)

    def test_tail_tables_need_this_schema_a_consistent_length_and_adapter(self):
        directory = self.program("5L-tide-five-loop-test", with_tail=True)
        good = (directory / ordered_cache.TAIL_FILE).read_bytes()
        for bad in (tail("saved-application", schema="rustred.ordered-tail.v2"), good[:-1],
                    tail("closed-artifact")):
            (directory / ordered_cache.TAIL_FILE).write_bytes(bad)
            with self.subTest(bad=bad[-20:]), self.assertRaises(ValueError):
                ordered_cache.stage_cache_dir(self.cache, self.root)
        (directory / ordered_cache.TAIL_FILE).write_bytes(good)
        ordered_cache.stage_cache_dir(self.cache, self.root)
        self.assertEqual(data.read_json(self.root / "5L/ordered-cache.json")["programs"][0]["tail_bytes"],
                         len(good))

    def test_declared_rustred_versions_must_match_the_files(self):
        self.program("4L-four-loop-h", with_tail=True)
        versions = {"ordered_step_cache_schema": ordered_cache.RUSTRED_CACHE_SCHEMA,
                    "ordered_step_semantics": "rustred-ordered-steps-2026-10-31",
                    "ordered_tail_schema": ordered_cache.TAIL_SCHEMA,
                    "ordered_tail_semantics": "rustred-ordered-tail-2026-10-31"}
        for key in versions:
            wrong = dict(versions, **{key: "other"})
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, key):
                ordered_cache.stage_cache_dir(self.cache, self.root, metadata={"producer": {"rustred": wrong}})
            # Refused before the pack is touched.
            self.assertFalse((self.root / "4L/ordered-cache").exists())
        ordered_cache.stage_cache_dir(self.cache, self.root, metadata={"producer": {"rustred": versions}})
        self.assertEqual(ordered_cache.validate(self.root)["4L"], 1)

    def test_files_above_the_git_file_limit_are_refused(self):
        self.program("3L-unit-mass-vacuum-k6")
        with patch.object(ordered_cache, "FILE_BYTES_LIMIT", 100), self.assertRaisesRegex(ValueError, "exceeds"):
            ordered_cache.stage_cache_dir(self.cache, self.root)

    def trimmed(self, base_bytes=None):
        directory = self.program("5L-tide-five-loop-test", with_tail=True)
        size, tail_size = shards_bytes(directory), (directory / ordered_cache.TAIL_FILE).stat().st_size
        trim = {"from_records": 100, "from_shards": 10, "from_bytes": 10 * size, "from_tail_bytes": tail_size,
                "method": "zero workload + first layered quadratic records", "full_cache": "download x"}
        if base_bytes is not None:
            trim.update(base_bytes=base_bytes, base_tail_bytes=tail_size)
        return {"programs": {"5L-tide-five-loop-test": {"complete": False, "trim": trim}}}, size, tail_size

    def test_trimmed_caches_declare_their_origin_and_count_their_increment_in_the_release_budget(self):
        metadata, size, tail_size = self.trimmed()
        broken = copy.deepcopy(metadata)
        del broken["programs"]["5L-tide-five-loop-test"]["trim"]["full_cache"]
        with self.assertRaisesRegex(ValueError, "trim"):
            ordered_cache.stage_cache_dir(self.cache, self.root, metadata=broken)
        broken = copy.deepcopy(metadata)
        broken["programs"]["5L-tide-five-loop-test"]["trim"] = None
        with self.assertRaisesRegex(ValueError, "trim"):
            ordered_cache.stage_cache_dir(self.cache, self.root, metadata=broken)
        ordered_cache.stage_cache_dir(self.cache, self.root, metadata=metadata)
        manifest = data.read_json(self.root / "manifest.json")
        # Without a declared base the whole trimmed cache counts.
        self.assertEqual(ordered_cache.light_bytes(self.root / "5L", self.loop(5)), size + tail_size)
        self.assertEqual(data.validate_release_cache_budget(self.root, manifest), size + tail_size)
        shutil.rmtree(self.cache)
        self.cache.mkdir()
        metadata, size, tail_size = self.trimmed(base_bytes=40)
        ordered_cache.stage_cache_dir(self.cache, self.root, metadata=metadata)
        manifest = data.read_json(self.root / "manifest.json")
        increment = size - 40
        self.assertEqual(ordered_cache.light_bytes(self.root / "5L", self.loop(5)), increment)
        with patch.object(data, "FIVE_LOOP_LIGHT_CACHE_BYTES_LIMIT", increment):
            self.assertEqual(data.validate_release_cache_budget(self.root, manifest), increment)
        with (
            patch.object(data, "FIVE_LOOP_LIGHT_CACHE_BYTES_LIMIT", increment - 1),
            self.assertRaisesRegex(ValueError, f"{increment} bytes.*{increment - 1}"),
        ):
            data.validate_release_cache_budget(self.root, manifest)

    def test_receipts_describe_caches_kept_outside_the_repository(self):
        directory = self.program("5L-tide-five-loop-test", with_tail=True)
        document = ordered_cache.receipt(directory, self.root, metadata={"producer": {"p": 1}})
        self.assertEqual(document["schema"], ordered_cache.RECEIPT_SCHEMA)
        self.assertEqual(document["directory"], directory.name)
        self.assertTrue(document["complete"])
        self.assertEqual(document["rule_tables"], self.tables(5)["5L-tide-five-loop-test"])
        self.assertEqual(set(document["files"]),
                         {path.relative_to(directory).as_posix() for path in directory.rglob("*") if path.is_file()})
        manifest_bytes = document["files"]["ordered-step-cache.txt"]["bytes"]
        self.assertEqual(document["bytes"] + document["tail_bytes"] + manifest_bytes,
                         sum(record["bytes"] for record in document["files"].values()))
        other = self.make_repo(self.base / "other")
        (other / "5L/ibps/application.json").write_text('{"application": 6}\n')
        loop = self.loop(5, other)
        loop["files"]["ibps/application.json"] = data.file_record(other / "5L/ibps/application.json")
        data.write_json(other / "5L/manifest.json", loop)
        with self.assertRaisesRegex(ValueError, "rule tables"):
            ordered_cache.receipt(directory, other)

    def test_route_preparation_entries_are_typed_listed_and_magic_checked(self):
        directory = self.root / "5L"
        (directory / "route-preparation.rrbin").write_bytes(data.ROUTE_PREPARATION_MAGIC + b"payload")
        loop = self.loop(5)
        loop["route_preparation"] = {"path": "route-preparation.rrbin", "format": data.ROUTE_PREPARATION_FORMAT}
        loop["files"]["route-preparation.rrbin"] = data.file_record(directory / "route-preparation.rrbin")
        self.assertEqual(data.validate_route_preparation(directory, loop), "route-preparation.rrbin")
        for key, value in (("format", "other"), ("path", "ibps/application.json"), ("path", "missing.rrbin")):
            broken = copy.deepcopy(loop)
            broken["route_preparation"][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                data.validate_route_preparation(directory, broken)
        (directory / "route-preparation.rrbin").write_bytes(b"not an add-on")
        with self.assertRaises(ValueError):
            data.validate_route_preparation(directory, loop)

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
