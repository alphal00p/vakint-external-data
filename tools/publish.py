#!/usr/bin/env python3
"""Publish a checked immutable release, then update the data-latest manifest."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

REPOSITORY = "alphal00p/vakint-external-data"
ROOT = Path(__file__).resolve().parents[1]


def run(*arguments):
    return subprocess.check_output(arguments, text=True, cwd=ROOT).strip()


def gh(*arguments):
    return run("gh", *arguments, "--repo", REPOSITORY)


def release(tag):
    result = subprocess.run(
        [
            "gh",
            "release",
            "view",
            tag,
            "--repo",
            REPOSITORY,
            "--json",
            "isDraft,tagName",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )
    if result.returncode == 0:
        return json.loads(result.stdout)
    if "not found" not in result.stderr.lower():
        raise RuntimeError(result.stderr.strip())
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    directory = args.directory.resolve()
    manifest = json.loads((directory / "manifest.json").read_text())
    source = json.loads((ROOT / "manifest.json").read_text())
    if manifest["version"] != source["version"] or {
        p["loop_count"]: p["manifest_sha256"] for p in manifest["loop_packs"]
    } != {p["loop_count"]: p["manifest_sha256"] for p in source["loop_packs"]}:
        raise RuntimeError(
            "release assets were not built from the committed source manifest"
        )
    version = manifest["version"]
    if run("git", "status", "--porcelain"):
        raise RuntimeError("commit the validated source tree before publishing")
    commit = run("git", "rev-parse", "HEAD")
    archives = []
    for pack in manifest["loop_packs"]:
        archive = directory / pack["archive"]
        with archive.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if (
            actual != pack["archive_sha256"]
            or archive.stat().st_size != pack["archive_bytes"]
        ):
            raise RuntimeError(f"release archive differs from manifest: {archive}")
        archives.append(str(archive))
    current = release(version)
    if current is not None and not current["isDraft"]:
        raise RuntimeError(
            f"immutable release {version} already published; do not overwrite it"
        )
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
