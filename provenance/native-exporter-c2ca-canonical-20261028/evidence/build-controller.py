"""Root-cleared Native-only producer build/parser/Clippy/build-info.

Prepared source only until exact --packet/--go identities are supplied. Reuses
established exact PIDFD50GB build control; no cache copy/index/IBP/data command.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import signal
import subprocess
import time
import traceback
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKSPACE = Path("/shared/codex-1/vakint_rustred/workspace")
CONTROL = (
    WORKSPACE / "5l-push/validation/heavy-five-source-finalization-20261027/control.py"
)
CONTROL_SHA = "e7f49d9f276fbdb0537360f77ba8c428a0bb6e2d5725811a3e5c1213255575ac"
OUT = HERE / "producer-build-run1"
DONOR = WORKSPACE / "build/heavy-native-finalization-ci-optim-c2ca"
TARGET = WORKSPACE / "build/native-producer-c2ca-v2-ci-optim"
MANIFEST = HERE / "producer-c2ca-source/Cargo.toml"
BASE = HERE
FLOOR = 50_000_000_000
NATIVE = "c2ca815cc906bdeaf7cb8c63b637e81a80fba917"
KERNEL = "9cd57678d8817ec33c05cacba4925162f1c86b0b"


def sha(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--packet", required=True)
parser.add_argument("--packet-sha256", required=True)
parser.add_argument("--go", required=True)
parser.add_argument("--go-sha256", required=True)
ARGS = parser.parse_args()
PACKET, GO = Path(ARGS.packet), Path(ARGS.go)
PACKET_SHA, GO_SHA = ARGS.packet_sha256, ARGS.go_sha256
assert sha(CONTROL) == CONTROL_SHA
spec = importlib.util.spec_from_file_location("sealed_existing_build_control", CONTROL)
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)  # Definitions only; originalmain neverruns.
assert sha(GO) == GO_SHA and sha(PACKET) == PACKET_SHA
APPROVAL, PROPOSAL = json.loads(GO.read_text()), json.loads(PACKET.read_text())
assert APPROVAL["approved"] is True and APPROVAL["packet_sha256"] == PACKET_SHA
assert APPROVAL["cpus"] == PROPOSAL["cpus"] and APPROVAL["jobs"] == 2
assert APPROVAL["minimum_machine_MemAvailable_bytes"] == FLOOR
assert all(
    APPROVAL[name] is False
    for name in [
        "union_copy_authorized",
        "cache_payload_reads_authorized",
        "reduction_authorized",
        "export_reimport_authorized",
        "publication_authorized",
    ]
)
EXPECTED = {row["path"]: row["sha256"] for row in PROPOSAL["source_files"]}
EXPECTED.update({str(GO): GO_SHA, str(PACKET): PACKET_SHA})
MARKER = "native-producer-build-only-" + uuid.uuid4().hex
ENV = os.environ.copy()
for key in list(ENV):
    if key.startswith("CARGO_PROFILE_") or key in {
        "CARGO_ENCODED_RUSTFLAGS",
        "RUSTFLAGS",
        "RUSTC_WRAPPER",
        "RUSTC_WORKSPACE_WRAPPER",
        "PYTHONPATH",
        "PYTHONHOME",
    }:
        ENV.pop(key, None)
ENV.update(
    CARGO_TARGET_DIR=str(TARGET),
    CARGO_BUILD_JOBS="2",
    CARGO_INCREMENTAL="0",
    RUSTFLAGS="",
    RAYON_NUM_THREADS="1",
    OMP_NUM_THREADS="1",
    MKL_NUM_THREADS="1",
    OPENBLAS_NUM_THREADS="1",
    NUMEXPR_NUM_THREADS="1",
    BLIS_NUM_THREADS="1",
    OMP_THREAD_LIMIT="1",
    TMPDIR=str(OUT / "tmp"),
    VAKINT_HEAVY_CONTROL_MARKER=MARKER,
)
RESULT = {
    "schema": "vakint.native-producer-build-only-controller.v1",
    "status": "running",
    "root_go_sha256": GO_SHA,
    "proposal_sha256": PACKET_SHA,
    "cpus": PROPOSAL["cpus"],
    "jobs": 2,
    "memory_floor_bytes": FLOOR,
    "marker": MARKER,
    "steps": [],
    "Main_linked": False,
    "cache_payload_reads_authorized": False,
    "union_copy_export_reimport_authorized": False,
}


def save(name, value):
    control.save_document(OUT / name, value)


def check_sources():
    for path, expected in EXPECTED.items():
        assert sha(path) == expected, "approved source/control changed: " + path


def compiler_preflight():
    matches = []
    for directory in Path("/proc").iterdir():
        if not directory.name.isdigit():
            continue
        try:
            executable = directory.joinpath("exe").resolve(strict=True).name
            if executable not in {
                "cargo",
                "rustc",
                "rustdoc",
                "clippy-driver",
                "maturin",
            }:
                continue
            command = (
                directory.joinpath("cmdline")
                .read_bytes()
                .replace(b"\0", b" ")
                .decode(errors="replace")
            )
            entries = directory.joinpath("environ").read_bytes().split(b"\0")
            target = next(
                (
                    entry.split(b"=", 1)[1].decode()
                    for entry in entries
                    if entry.startswith(b"CARGO_TARGET_DIR=")
                ),
                None,
            )
            if (
                target in {str(DONOR), str(TARGET)}
                or str(DONOR) in command
                or str(TARGET) in command
            ):
                matches.append(
                    {
                        "pid": int(directory.name),
                        "executable": executable,
                        "argv": command,
                        "target": target,
                    }
                )
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            pass
    assert not matches, matches
    return matches


def run(name, argv, *, stdout_file=None, extra_env=None):
    check_sources()
    assert control.mem_available() >= FLOOR
    owned = control.OwnedProcesses(MARKER)
    environment = ENV.copy()
    if extra_env:
        environment.update(extra_env)
    start = time.monotonic()
    step = {
        "name": name,
        "argv": list(map(str, argv)),
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    child = None
    minimum = control.mem_available()
    max_rss = None
    max_hwm = None
    max_sum = None
    try:
        with (OUT / (name + ".log")).open("xb") as log:
            stream = (OUT / stdout_file).open("xb") if stdout_file else log
            try:
                child = subprocess.Popen(
                    list(map(str, argv)),
                    cwd=BASE,
                    env=environment,
                    stdout=stream,
                    stderr=log,
                    start_new_session=True,
                )
                step["child"] = owned.attach_child(child)
                save("active-step.json", step)
                while child.poll() is None:
                    available = control.mem_available()
                    minimum = min(minimum, available)
                    assert available >= FLOOR, (
                        "MemAvailable below50GB; stopping exact owned child cohort"
                    )
                    owned.collect()
                    memory = owned.memory(child.pid)
                    current = memory.get("child")
                    if current:
                        if current.get("rss_bytes") is not None:
                            max_rss = max(max_rss or 0, current["rss_bytes"])
                        if current.get("vmhwm_bytes") is not None:
                            max_hwm = max(max_hwm or 0, current["vmhwm_bytes"])
                    if memory["cohort_rss_sum_bytes"] is not None:
                        max_sum = max(max_sum or 0, memory["cohort_rss_sum_bytes"])
                    disk = os.statvfs(WORKSPACE)
                    disk_free = disk.f_bavail * disk.f_frsize
                    assert disk_free >= 100_000_000_000, (
                        "workspacefree below explicit100GB reserve"
                    )
                    save(
                        "resource.json",
                        {
                            "phase": name,
                            "sample_unix_seconds": time.time(),
                            "mem_available_bytes": available,
                            "minimum_mem_available_bytes": minimum,
                            "disk_available_bytes": disk_free,
                            "owned_memory": memory,
                        },
                    )
                    time.sleep(1)
                step["returncode"] = child.returncode
                assert child.returncode == 0, name + " child failed; preserved log"
                assert not owned.live(), "successful child left marked descendants"
            finally:
                if stdout_file:
                    stream.close()
        check_sources()
    except BaseException:
        if child is not None:
            owned.stop(child)
            step["returncode"] = child.returncode
        raise
    finally:
        step.update(
            seconds=time.monotonic() - start,
            minimum_mem_available_bytes=minimum,
            maximum_observed_child_rss_bytes=max_rss,
            maximum_observed_child_vmhwm_bytes=max_hwm,
            maximum_observed_cohort_rss_sum_bytes=max_sum,
            signals=owned.signals,
            log_sha256=sha(OUT / (name + ".log")),
        )
        owned.close()
        RESULT["steps"].append(step)
        save("result.json", RESULT)


def validate_metadata():
    metadata = json.loads((OUT / "cargo-metadata.json").read_text())
    groups = {}
    for name, rev in [
        (name, NATIVE) for name in ["rustred", "rustred-app", "rustred-order"]
    ] + [(name, KERNEL) for name in ["symbolica", "numerica", "graphica"]]:
        rows = [p for p in metadata["packages"] if p["name"] == name]
        assert len(rows) == 1 and rev in (rows[0]["source"] or ""), (name, rows)
        groups[name] = {k: rows[0][k] for k in ["id", "source", "manifest_path"]}
    assert not any(
        p["name"] in {"vakint", "gammalooprs", "feynkit"} for p in metadata["packages"]
    )
    for name, version in PROPOSAL["registry_versions"].items():
        assert any(
            p["name"] == name and p["version"] == version for p in metadata["packages"]
        ), (name, version)
    save(
        "metadata-owner-proof.json",
        {
            "one_owner_each": groups,
            "Main_linked": False,
            "lock_sha256": sha(MANIFEST.parent / "Cargo.lock"),
            "metadata_sha256": sha(OUT / "cargo-metadata.json"),
            "resolve_nodes": metadata["resolve"]["nodes"],
        },
    )


def inventory_actual_inputs(artifacts):
    # Reuse the already independently reviewed Make-depfile parser. Only its
    # definitions are imported; its old hardcoded main/run is never invoked.
    parser_path = Path(PROPOSAL["depfile_parser"]["path"])
    assert sha(parser_path) == PROPOSAL["depfile_parser"]["sha256"]
    module_spec = importlib.util.spec_from_file_location(
        "reviewed_native_depfile_parser", parser_path
    )
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    meta = json.loads((OUT / "cargo-metadata.json").read_text())
    by_id = {p["id"]: p for p in meta["packages"]}
    native = Path(PROPOSAL["Native_identity_worktree"])
    expected = {
        "rustred": native / "crates/rustred-core",
        "rustred-app": native / "crates/rustred-app",
        "rustred-order": native / "crates/rustred-order",
        "symbolica": native / "vendor/symbolica",
        "graphica": native / "vendor/symbolica/lib/graphica",
        "numerica": native / "vendor/symbolica/lib/numerica",
    }
    owners = {
        name: next(p for p in meta["packages"] if p["name"] == name)
        for name in expected
    }
    inputs = {}
    depfiles = {}
    owner_matches = {name: 0 for name in expected}
    artifact_coverage = []
    for artifact in artifacts:
        candidates = sorted(module.depfile_candidates(artifact))
        present = [path for path in candidates if path.is_file()]
        assert present, (
            "missing actualartifact depfile",
            artifact["package_id"],
            artifact["target"],
            list(map(str, candidates)),
        )
        artifact_coverage.append(
            {
                "package_id": artifact["package_id"],
                "target": artifact["target"],
                "features": artifact["features"],
                "profile": artifact["profile"],
                "fresh": artifact["fresh"],
                "actual_depfiles": list(map(str, present)),
            }
        )
        for dep in present:
            key = str(dep)
            if key in depfiles:
                continue
            rules, environment = module.dep_rules(dep)
            depfiles[key] = {
                "sha256": sha(dep),
                "environment_values_redacted": environment,
                "package_id": artifact["package_id"],
                "features": artifact["features"],
                "profile": artifact["profile"],
                "fresh": artifact["fresh"],
            }
            for rule in rules:
                for name in rule["inputs"]:
                    path = Path(name)
                    if not path.is_absolute():
                        package_root = Path(
                            by_id[artifact["package_id"]]["manifest_path"]
                        ).parent
                        candidates = {
                            candidate.resolve()
                            for candidate in [
                                BASE / path,
                                MANIFEST.parent / path,
                                package_root / path,
                            ]
                            if candidate.is_file()
                        }
                        assert len(candidates) == 1, (
                            name,
                            sorted(map(str, candidates)),
                        )
                        path = candidates.pop()
                    path = path.resolve()
                    assert not any(
                        str(path).startswith(prefix)
                        for prefix in PROPOSAL["forbidden_scientific_data_roots"]
                    ), "compiledinput unexpectedlyreferences scientificpayload"
                    assert path.is_file(), path
                    if str(path) not in inputs:
                        inputs[str(path)] = {
                            "sha256": sha(path),
                            "bytes": path.stat().st_size,
                        }
                    for owner, package in owners.items():
                        root = Path(package["manifest_path"]).parent
                        if path.is_relative_to(root):
                            relative = path.relative_to(root)
                            truth = expected[owner] / relative
                            assert (
                                truth.is_file()
                                and sha(truth) == inputs[str(path)]["sha256"]
                            ), (owner, str(path), str(truth))
                            owner_matches[owner] += 1
    assert all(owner_matches.values()), owner_matches
    save(
        "actual-compiler-input-inventory.json",
        {
            "schema": "vakint.native-producer-actual-inputs.v1",
            "Main_linked": False,
            "one_actual_owner_each": {
                n: {k: p[k] for k in ["id", "source", "manifest_path"]}
                for n, p in owners.items()
            },
            "owner_tracked_input_matches": owner_matches,
            "artifact_depfile_coverage": artifact_coverage,
            "depfiles": depfiles,
            "inputs": inputs,
            "qualification": "ActualCargoartifact/depfile/sourceinputs withfresh/reusedorigins andrealfeatures/profiles; no source-ID relabel, private sourcepatch or scientificpayload. .d envvalues hashed/redacted.",
        },
    )


def interrupted(signum, _frame):
    raise KeyboardInterrupt(f"controller signal {signum}")


signal.signal(signal.SIGTERM, interrupted)
signal.signal(signal.SIGINT, interrupted)
OUT.mkdir(exist_ok=False)
(OUT / "tmp").mkdir()
try:
    os.sched_setaffinity(0, set(PROPOSAL["cpus"]))
    RESULT["controller"] = control.process_identity(os.getpid())
    RESULT["controller_sha256"] = sha(Path(__file__))
    RESULT["approved_input_hashes"] = EXPECTED
    check_sources()
    compiler_preflight()
    assert DONOR.is_dir() and not TARGET.exists()
    probe = DONOR / "ci-optim/heavy-native-finalizer"
    before = probe.stat()
    assert (
        sha(probe) == "558a309620eaac6522fbfa863744e9952659798c04cca350e87e15deb99d7359"
    )
    run("copy-readonly-c2ca-donor", ["cp", "-a", "--reflink=auto", DONOR, TARGET])
    copied = TARGET / probe.relative_to(DONOR)
    assert (
        probe.stat().st_ino == before.st_ino and copied.stat().st_ino != before.st_ino
    )
    save(
        "donor-copy-proof.json",
        {
            "donor": str(DONOR),
            "target": str(TARGET),
            "independent_inodes_optional_reflink": True,
            "primary_source_unchanged": sha(probe) == sha(copied),
            "original_live_export_ELF_unmodified": True,
        },
    )
    # Start from the authentic immutable03 dependency version set, then let
    # ordinary Cargo resolve this new root package; never relabel the seed as
    # the actual lock. No workspace/root lock is modified.
    seed = Path(PROPOSAL["Main03_lock_seed"]["path"])
    assert sha(seed) == PROPOSAL["Main03_lock_seed"]["sha256"]
    lock = MANIFEST.parent / "Cargo.lock"
    assert not lock.exists()
    run("seed-authentic03-lock", ["cp", seed, lock])
    run(
        "ordinary-private-resolver",
        [
            "cargo",
            "metadata",
            "--offline",
            "--format-version",
            "1",
            "--manifest-path",
            MANIFEST,
        ],
        stdout_file="cargo-metadata.json",
    )
    validate_metadata()
    run(
        "build-producer",
        [
            "cargo",
            "build",
            "--locked",
            "--offline",
            "--profile",
            "ci-optim",
            "--manifest-path",
            MANIFEST,
            "--bin",
            "native-selected-cache-producer",
            "--message-format=json-render-diagnostics",
        ],
        stdout_file="cargo-artifacts.jsonl",
    )
    records = []
    for line in (OUT / "cargo-artifacts.jsonl").read_text().splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("reason") == "compiler-artifact":
            records.append(item)
    save("all-cargo-artifacts.json", records)
    rows = [
        r
        for r in records
        if r["target"]["name"] == "native-selected-cache-producer"
        and r.get("executable")
    ]
    assert len(rows) == 1
    row = rows[0]
    binary = Path(row["executable"])
    with binary.open("rb") as stream:
        assert stream.read(4) == b"\x7fELF"
    primary = {
        "path": str(binary),
        "sha256": sha(binary),
        "bytes": binary.stat().st_size,
        "Cargo_profile": row["profile"],
        "fresh": row["fresh"],
        "target": row["target"],
    }
    assert row["profile"]["opt_level"] == "2" and not row["profile"]["test"]
    save("primary-artifact.json", primary)
    run(
        "parser-tests",
        [
            "cargo",
            "test",
            "--locked",
            "--offline",
            "--profile",
            "ci-optim",
            "--manifest-path",
            MANIFEST,
            "--bin",
            "native-selected-cache-producer",
            "--",
            "--test-threads=1",
        ],
    )
    run(
        "clippy",
        [
            "cargo",
            "clippy",
            "--locked",
            "--offline",
            "--profile",
            "ci-optim",
            "--manifest-path",
            MANIFEST,
            "--bin",
            "native-selected-cache-producer",
            "--all-targets",
            "--no-deps",
            "--",
            "-D",
            "warnings",
        ],
    )
    run("build-info", [binary, "build-info"], stdout_file="build-info.json")
    info = json.loads((OUT / "build-info.json").read_text())
    assert sha(binary) == primary["sha256"]
    assert info["measurement_executable_sha256"] == primary["sha256"]
    assert (
        info["native_revision"] == info["main_revision"] == NATIVE
        and info["kernel_revision"] == KERNEL
    )
    assert info["source_identity"]["native_identity"]["clean"] is True
    assert info["source_identity"]["native_identity"]["codec_state_format"] == 6
    for name, checksum in info["source_identity"]["files"].items():
        assert sha(MANIFEST.parent / name) == checksum
    inventory_actual_inputs(records)
    # Actual build-info layout/cohort is preserved rather than fabricated here.
    save(
        "actual-source-freeze-after-lock.json",
        {
            name: {
                "sha256": sha(MANIFEST.parent / name),
                "bytes": (MANIFEST.parent / name).stat().st_size,
            }
            for name in [
                "Cargo.toml",
                "Cargo.lock",
                "build.rs",
                "src/main.rs",
                "src/union.rs",
                "src/selection.rs",
                "src/index_identity.rs",
                "src/proof_reference.rs",
                "src/resource_guard_admission.rs",
            ]
        },
    )
    RESULT.update(
        status="BUILD_PARSER_CLIPPY_BUILDINFO_PASS_NO_CACHE_RUNTIME",
        primary_artifact=primary,
        build_info_sha256=sha(OUT / "build-info.json"),
        cohort_info_keys=list(info),
    )
except BaseException as error:
    RESULT.update(
        status="FAILED_PRESERVED_NO_CACHE_RUNTIME",
        error=type(error).__name__ + ": " + str(error),
    )
    traceback.print_exc()
    raise
finally:
    RESULT["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save("result.json", RESULT)
raise SystemExit(
    0
    if RESULT["status"] == "BUILD_PARSER_CLIPPY_BUILDINFO_PASS_NO_CACHE_RUNTIME"
    else 1
)
