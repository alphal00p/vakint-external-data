#!/usr/bin/env python3
"""Publish a checked immutable release, then update the data-latest manifest."""

import argparse
import copy
import hashlib
import json
import subprocess
from pathlib import Path
from urllib.parse import quote

import data

REPOSITORY = "alphal00p/vakint-external-data"
RELEASE_ASSET_COUNT_LIMIT = 1000
ROOT = Path(__file__).resolve().parents[1]


def run(*arguments):
    return subprocess.check_output(arguments, text=True, cwd=ROOT).strip()


def gh(*arguments):
    return run("gh", *arguments, "--repo", REPOSITORY)


def query(*arguments):
    result = subprocess.run(
        ["gh", *arguments],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )
    if result.returncode == 0:
        return json.loads(result.stdout)
    if not any(marker in result.stderr.lower() for marker in ("not found", "http 404")):
        raise RuntimeError(result.stderr.strip())
    return None


def release(tag):
    return query(
        "release",
        "view",
        tag,
        "--repo",
        REPOSITORY,
        "--json",
        "isDraft,tagName,targetCommitish",
    )


def check_release_target(version, commit, current):
    """A pre-existing tag or resumed draft must describe this exact source commit."""
    endpoint = f"repos/{REPOSITORY}"
    reference = query("api", f"{endpoint}/git/ref/tags/{quote(version, safe='')}")
    if reference is None:
        if current is None:
            return
        target = current.get("targetCommitish", "")
        resolved = (
            query("api", f"{endpoint}/commits/{quote(target, safe='')}")
            if target
            else None
        )
        if resolved is None or resolved.get("sha") != commit:
            raise RuntimeError(
                "existing release draft does not target the committed source HEAD"
            )
        return
    target = reference["object"]
    seen = set()
    while target["type"] == "tag":
        if target["sha"] in seen or len(seen) >= 16:
            raise RuntimeError("invalid or excessively nested immutable release tag")
        seen.add(target["sha"])
        annotated = query("api", f"{endpoint}/git/tags/{target['sha']}")
        if annotated is None:
            raise RuntimeError("annotated immutable release tag could not be resolved")
        target = annotated["object"]
    if target["type"] != "commit" or target["sha"] != commit:
        raise RuntimeError(
            "existing immutable release tag does not target the committed source HEAD"
        )


def checked_assets(directory, manifest, source):
    """Allow only generated archive identities to differ from committed metadata."""
    marker = directory / data.RUNTIME_ONLY_MARKER
    if marker.exists() or marker.is_symlink():
        raise RuntimeError("runtime-only validation packs are not publishable; rebuild in full mode")
    identity = copy.deepcopy(manifest)
    for pack in identity["loop_packs"]:
        pack["archive_sha256"] = None
        pack["archive_bytes"] = None
    if (
        source.get("schema") != "vakint.external-data.v1"
        or [p["loop_count"] for p in source["loop_packs"]] != list(range(1, 6))
        or identity != source
    ):
        raise RuntimeError(
            "release assets were not built from the committed source manifest"
        )
    try:
        evidence = data.provenance_assets(manifest)
        runtime = data.runtime_cache_assets(ROOT, manifest)
        descriptors = data.runtime_descriptor_assets(manifest)
    except ValueError as error:
        raise RuntimeError(str(error)) from error
    assets = [*manifest["loop_packs"], *evidence, *runtime, *descriptors]
    if any(not data.valid_archive_bytes(asset["archive_bytes"]) for asset in assets):
        raise RuntimeError("release archive sizes must be positive integers smaller than 2 GB")
    expected_files = {asset["archive"] for asset in assets} | {"manifest.json", "SHA256SUMS"}
    if len(expected_files) > RELEASE_ASSET_COUNT_LIMIT:
        raise RuntimeError("release exceeds the 1000-asset hosting allowance")
    if {path.name for path in directory.iterdir()} - expected_files:
        raise RuntimeError("release directory differs from the complete declared asset inventory")
    archives = []
    checksums = {}
    for pack in assets:
        name = pack["archive"]
        if (
            "loop_count" in pack
            and name
            != f"vakint-external-data-{manifest['version']}-{pack['loop_count']}L.tar.gz"
        ):
            raise RuntimeError(f"unexpected release archive name: {name}")
        archive = directory / name
        if archive.is_symlink() or not archive.is_file():
            raise RuntimeError(f"release archive is not a regular file: {archive}")
        if archive.stat().st_size != pack["archive_bytes"]:
            raise RuntimeError(f"release archive differs from manifest: {archive}")
        with archive.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != pack["archive_sha256"]:
            raise RuntimeError(f"release archive differs from manifest: {archive}")
        checksums[name] = actual
        archives.append(str(archive))
    # Recheck the container/member inventory at the publication boundary as well
    # as during packaging. Metadata checks alone do not authenticate tar members.
    if runtime:
        import nativepack

        for reference in manifest.get("runtime_cache_snapshots", []):
            nativepack.verify_archives(nativepack.validate_reference(ROOT, reference), directory)
    checksums["manifest.json"] = hashlib.sha256(
        (directory / "manifest.json").read_bytes()
    ).hexdigest()
    expected = "".join(f"{checksums[name]}  {name}\n" for name in sorted(checksums))
    if (directory / "SHA256SUMS").read_text() != expected:
        raise RuntimeError(
            "SHA256SUMS differs from the complete release asset inventory"
        )
    return archives


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    directory = args.directory.resolve()
    manifest = json.loads((directory / "manifest.json").read_text())
    source = json.loads((ROOT / "manifest.json").read_text())
    archives = checked_assets(directory, manifest, source)
    version = manifest["version"]
    if run("git", "status", "--porcelain"):
        raise RuntimeError("commit the validated source tree before publishing")
    commit = run("git", "rev-parse", "HEAD")
    current = release(version)
    if current is not None and not current["isDraft"]:
        raise RuntimeError(
            f"immutable release {version} already published; do not overwrite it"
        )
    check_release_target(version, commit, current)
    if current is None:
        gh(
            "release",
            "create",
            version,
            "--target",
            commit,
            "--draft",
            "--title",
            version,
            "--notes",
            "Versioned per-loop Vakint IBPs, master coefficients, graphs and prepared caches. Requesting N loops loads all packs from 1L through N. Five-loop terminals remain uncomputed.",
        )
    gh(
        "release",
        "upload",
        version,
        *archives,
        str(directory / "manifest.json"),
        str(directory / "SHA256SUMS"),
        "--clobber",
    )
    gh("release", "edit", version, "--draft=false", "--latest")
    if release("data-latest") is None:
        gh(
            "release",
            "create",
            "data-latest",
            "--target",
            commit,
            "--prerelease",
            "--latest=false",
            "--title",
            "Latest official data",
            "--notes",
            f"Current immutable version: {version}.",
        )
    # Archive names contain the immutable version. Keep previous archives so an
    # in-flight client holding the previous manifest remains able to fetch them.
    gh("release", "upload", "data-latest", *archives, "--clobber")
    gh("release", "upload", "data-latest", str(directory / "SHA256SUMS"), "--clobber")
    gh(
        "release",
        "upload",
        "data-latest",
        str(directory / "manifest.json"),
        "--clobber",
    )
    gh(
        "release",
        "edit",
        "data-latest",
        "--notes",
        f"Current immutable version: {version}.",
    )
    print(f"https://github.com/{REPOSITORY}/releases/tag/{version}")
    print(f"https://github.com/{REPOSITORY}/releases/tag/data-latest")


if __name__ == "__main__":
    main()
