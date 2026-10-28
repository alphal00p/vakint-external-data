"""Two ordinary Cargo release collectors, using only a private copy of03 artifacts."""

import fcntl
import json
import os
import shutil
import subprocess
from pathlib import Path

from control import reference, require, save, sha, source_check

PLAN = Path(os.environ["VAKINT_FINAL_Q0_PLAN"])
require(sha(PLAN) == os.environ["VAKINT_FINAL_Q0_PLAN_SHA256"], "plan changed")
P = json.loads(PLAN.read_text())
OUT = Path(os.environ["VAKINT_FINAL_Q0_PHASE_OUTPUT"])
ROOT = source_check(P)
B = P["build"]
DONOR, TARGET = Path(B["donor"]), Path(B["target"])
CARGO, RUSTC = Path(B["compiler_tools"]) / "cargo", Path(B["compiler_tools"]) / "rustc"
require(not TARGET.exists(), "private target must be new")
require(
    os.environ.get("IN_NIX_SHELL") in ("impure", "pure"),
    "launch this build through the final source's normal nix develop",
)
require(not any(k.startswith("CARGO_PROFILE_") for k in os.environ), "profile override")
require(
    not any(
        os.environ.get(k)
        for k in (
            "CARGO_ENCODED_RUSTFLAGS",
            "RUSTC_WRAPPER",
            "RUSTC_WORKSPACE_WRAPPER",
        )
    ),
    "unexpected inherited compiler override",
)
require(
    os.environ.get("RUSTFLAGS") in (None, "", "-C linker=" + B["gcc"]),
    "unexpected inherited compiler flags",
)
authorities = {
    name: json.loads(reference(item).read_text())
    for name, item in B["donor_authorities"].items()
}
require(authorities["result"]["status"] == "PASS_BUILD_ONLY", "03 donor incomplete")
require(
    authorities["result"]["source_head"]
    == authorities["release_elfs"]["source_head"]
    == B["donor_head"],
    "donor source differs",
)
require(authorities["result"]["target"] == str(DONOR), "donor target differs")
require(
    authorities["result"]["release_elfs_sha256"]
    == B["donor_authorities"]["release_elfs"]["sha256"],
    "donor receipt chain differs",
)
require(authorities["release_elfs"]["profile"] == "release", "nonrelease donor")
donor_proof = authorities["compile_proof"]
require(
    authorities["release_elfs"]["compile_proof"] == donor_proof,
    "donor compiler proof chain differs",
)
require(
    donor_proof["VAKINT_CACHE_BUILD_RUSTRED_REVISION"] == B["native_revision"]
    and donor_proof["VAKINT_CACHE_BUILD_SYMBOLICA_REVISION"] == B["kernel_revision"]
    and donor_proof["VAKINT_CACHE_BUILD_PROFILE"] == "release",
    "donor dependency/profile differs",
)
require(
    set(authorities["release_elfs"]["features"]) == set(B["features"].split(",")),
    "donor feature union differs",
)


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def stats(root):
    result = {}
    for path in root.rglob("*"):
        require(not path.is_symlink(), "donor build tree contains a symlink")
        if path.is_file():
            stat = path.stat()
            result[str(path.relative_to(root))] = {
                "dev": stat.st_dev,
                "inode": stat.st_ino,
                "bytes": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "mode": stat.st_mode,
            }
    return result


def inventory(root, revision):
    require(git(root, "rev-parse", "HEAD") == revision, "owner revision changed")
    require(
        not git(root, "status", "--porcelain", "--untracked-files=no"),
        "owner source dirty",
    )
    rows = {}
    for raw in subprocess.check_output(
        ["git", "-C", str(root), "ls-files", "-z"]
    ).split(b"\0"):
        if not raw:
            continue
        name = os.fsdecode(raw)
        path = root / name
        if path.is_symlink():
            rows[name] = {"kind": "symlink", "target": os.readlink(path)}
        elif path.is_file():
            rows[name] = {
                "kind": "file",
                "bytes": path.stat().st_size,
                "sha256": sha(path),
            }
        else:
            rows[name] = {
                "kind": "gitlink",
                "tree_entry": git(root, "ls-tree", "HEAD", "--", name),
            }
    return {
        "schema": "vakint.actual-tracked-source-snapshot.v1",
        "source_root": str(root),
        "revision": revision,
        "tree": git(root, "rev-parse", "HEAD^{tree}"),
        "files": rows,
    }


with (DONOR / "release/.cargo-lock").open("rb") as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    before = stats(DONOR)
    for name in B["examples"]:
        artifact = authorities["release_elfs"]["artifacts"][name]
        require(
            artifact["actual_rustc"]["compiler"] == str(RUSTC)
            and "linker=" + B["gcc"] in artifact["actual_rustc"]["codegen_flags"],
            "donor compiler/linker differs",
        )
        require(
            sha(DONOR / "release/examples" / name) == artifact["target_sha256"],
            "03 donor ELF changed",
        )
    subprocess.run(
        [
            "cp",
            "-R",
            "--reflink=auto",
            "--preserve=mode,timestamps",
            str(DONOR),
            str(TARGET),
        ],
        check=True,
    )
    after, copied = stats(DONOR), stats(TARGET)
    require(before == after and before.keys() == copied.keys(), "donor copy changed")
    require(
        all(
            row["bytes"] == copied[name]["bytes"]
            and (row["dev"], row["inode"])
            != (copied[name]["dev"], copied[name]["inode"])
            for name, row in before.items()
        ),
        "private target is not an independent-inode copy",
    )
    save(
        OUT / "donor-copy.json",
        {
            "status": "PASS",
            "files": len(before),
            "logical_bytes": sum(row["bytes"] for row in before.values()),
            "donor_original_metadata_unchanged": True,
            "all_regular_inodes_independent": True,
        },
    )
env = os.environ.copy()
env.update(
    CARGO_TARGET_DIR=str(TARGET),
    CARGO_HOME=P["cargo_home"],
    CARGO_BUILD_JOBS=str(B["cargo_jobs"]),
    RUSTC=str(RUSTC),
    TMPDIR=str(OUT / "tmp"),
    TEMP=str(OUT / "tmp"),
    TMP=str(OUT / "tmp"),
)
(OUT / "tmp").mkdir()
version = subprocess.check_output([str(RUSTC), "-Vv"], text=True)
require(
    version == authorities["release_elfs"]["rustc_vv"]
    and version.splitlines()[0] == donor_proof["VAKINT_CACHE_BUILD_RUSTC"],
    "actual compiler differs from03 donor",
)
(OUT / "rustc-version.txt").write_text(version)
metadata_command = [
    str(CARGO),
    "metadata",
    "--locked",
    "--offline",
    "--no-default-features",
    "--features",
    B["features"],
    "--manifest-path",
    "crates/vakint/Cargo.toml",
    "--format-version",
    "1",
]
metadata = subprocess.check_output(metadata_command, cwd=ROOT, env=env)
(OUT / "metadata.json").write_bytes(metadata)
resolved = json.loads(metadata)
owners = {}
for name, expected in {
    "rustred": B["native_revision"],
    "rustred-app": B["native_revision"],
    "rustred-order": B["native_revision"],
    "symbolica": B["kernel_revision"],
    "numerica": B["kernel_revision"],
    "graphica": B["kernel_revision"],
}.items():
    matches = [pkg for pkg in resolved["packages"] if pkg["name"] == name]
    require(
        len(matches) == 1 and expected in matches[0]["source"], "owner closure differs"
    )
    owners[name] = matches[0]
native_root = Path(owners["rustred-app"]["manifest_path"]).parents[2]
save(OUT / "main-source-snapshot.json", inventory(ROOT, P["frozen_source"]["head"]))
save(OUT / "native-source-snapshot.json", inventory(native_root, B["native_revision"]))
proof = {
    "VAKINT_CACHE_BUILD_GIT_REVISION": P["frozen_source"]["head"],
    "VAKINT_CACHE_BUILD_RUSTRED_REVISION": B["native_revision"],
    "VAKINT_CACHE_BUILD_SYMBOLICA_REVISION": B["kernel_revision"],
    "VAKINT_CACHE_BUILD_MAIN_SOURCE_SNAPSHOT_SHA256": sha(
        OUT / "main-source-snapshot.json"
    ),
    "VAKINT_CACHE_BUILD_NATIVE_SOURCE_SNAPSHOT_SHA256": sha(
        OUT / "native-source-snapshot.json"
    ),
    "VAKINT_CACHE_BUILD_RUSTC": version.splitlines()[0],
    "VAKINT_CACHE_BUILD_PROFILE": "release",
}
save(OUT / "compile-proof-environment.json", proof)
save(
    OUT / "loader-environment.json",
    {
        "schema": "vakint.actual-release-loader-environment.v1",
        "source_head": P["frozen_source"]["head"],
        "variables": {
            name: {"is_set": name in env, "value": env.get(name)}
            for name in ("LD_LIBRARY_PATH", "LD_PRELOAD")
        },
        "license_presence_only": bool(env.get("SYMBOLICA_LICENSE")),
    },
)
env.update(proof)
env.update(
    RUSTFLAGS="-C linker=" + B["gcc"],
    RUSTC_WRAPPER=str(reference(B["rustc_recorder"])),
    VAKINT_RELEASE_RUSTC_LOG=str(OUT / "actual-rustc.jsonl"),
)
# Preserve03 Native/third-party artifacts. Cargo decides reuse from the actual
# final lock/features; only Vakint is forced fresh to prevent stamp/source aliasing.
subprocess.run(
    [
        str(CARGO),
        "clean",
        "--locked",
        "--offline",
        "--profile",
        "release",
        "-p",
        "vakint",
    ],
    cwd=ROOT,
    env=env,
    check=True,
)
command = [
    str(CARGO),
    "build",
    "--locked",
    "--offline",
    "--release",
    "-p",
    "vakint",
    "--no-default-features",
    "--features",
    B["features"],
    *[arg for name in B["examples"] for arg in ("--example", name)],
    "--message-format=json-render-diagnostics",
]
with (
    (OUT / "cargo-build.jsonl").open("xb") as log,
    (OUT / "cargo-build.stderr.log").open("xb") as errors,
):
    subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=errors, check=True)
records = [
    json.loads(line)
    for line in (OUT / "cargo-build.jsonl").read_text().splitlines()
    if line.startswith("{")
]
require(
    any(
        row.get("reason") == "build-finished" and row.get("success") for row in records
    ),
    "missing successful Cargo finish",
)
rustc = [
    json.loads(line) for line in (OUT / "actual-rustc.jsonl").read_text().splitlines()
]
artifacts = {}
(OUT / "artifacts").mkdir()
for name in B["examples"]:
    rows = [
        row
        for row in records
        if row.get("reason") == "compiler-artifact"
        and row.get("target", {}).get("name") == name
        and row.get("executable")
    ]
    compilers = [row for row in rustc if row["crate_name"] == name]
    require(
        len(rows) == len(compilers) == 1 and not rows[0]["fresh"],
        "collector was not fresh",
    )
    row, compiler = rows[0], compilers[0]
    profile = row["profile"]
    require(
        profile["opt_level"] == "3"
        and not profile["debug_assertions"]
        and not profile["overflow_checks"]
        and not profile["test"],
        "wrong release profile",
    )
    require(
        {"opt-level=3", "lto=fat"} <= set(compiler["codegen_flags"]),
        "missing actual3/fat codegen",
    )
    suffix = next(
        flag.split("=", 1)[1]
        for flag in compiler["codegen_flags"]
        if flag.startswith("extra-filename=")
    )
    dep = TARGET / "release/examples" / (name + suffix + ".d")
    dep_text = dep.read_text()
    for key, value in proof.items():
        require(
            [
                line
                for line in dep_text.splitlines()
                if line.startswith("# env-dep:" + key + "=")
            ]
            == ["# env-dep:" + key + "=" + value],
            "actual collector env stamp differs",
        )
    binary = Path(row["executable"])
    require(binary == TARGET / "release/examples" / name, "wrong collector path")
    preserved = OUT / "artifacts" / name
    shutil.copy2(binary, preserved)
    shutil.copy2(dep, OUT / "artifacts" / (name + ".d"))
    require(preserved.stat().st_ino != binary.stat().st_ino, "artifact hardlink")
    artifacts[name] = {
        "path": str(preserved),
        "sha256": sha(preserved),
        "bytes": preserved.stat().st_size,
        "cargo_artifact": row,
        "actual_rustc": compiler,
        "env_stamps": proof,
        "dep_info_sha256": sha(OUT / "artifacts" / (name + ".d")),
    }
    help_text = subprocess.check_output(
        [str(preserved), "--help"], cwd=ROOT, env=env, text=True
    )
    (OUT / (name + "-help.txt")).write_text(help_text)
    require(
        "--progress-snapshot" in help_text and "--monitor" in help_text,
        "monitor CLI missing",
    )
source_check(P)
save(
    OUT / "release-collectors.json",
    {
        "schema": "vakint.final-two-release-collectors.v1",
        "status": "PASS",
        "source_head": P["frozen_source"]["head"],
        "profile": "release",
        "profile_overrides": [],
        "normal_nix_develop": {
            "IN_NIX_SHELL": os.environ["IN_NIX_SHELL"],
            "source_flake_sha256": sha(ROOT / "flake.nix"),
            "source_flake_lock_sha256": sha(ROOT / "flake.lock"),
        },
        "linker_rustflags": ["-C", "linker=" + B["gcc"]],
        "command": command,
        "compile_proof": proof,
        "rustc_vv": version,
        "features": B["features"].split(","),
        "metadata_sha256": sha(OUT / "metadata.json"),
        "artifacts": artifacts,
        "dependency_cargo_artifacts": [
            row
            for row in records
            if row.get("reason") == "compiler-artifact"
            and any(row.get("package_id") == pkg["id"] for pkg in owners.values())
        ],
        "reused_dependency_provenance": B["donor_authorities"],
        "reused_dependencies_are_not_claimed_fresh": True,
        "freshly_compiled_crates": sorted({row["crate_name"] for row in rustc}),
        "physical_executions": 0,
        "cache_imports": 0,
        "cache_writes": 0,
        "nixci_result_claim": False,
    },
)
print(
    json.dumps({"status": "PASS_BUILD_ONLY", "collectors": list(artifacts)}), flush=True
)
