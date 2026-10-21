#!/usr/bin/env python3
"""Update project versions, commit the bump, and create a local release tag."""

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILES = (
    Path("extension/manifest.json"),
    Path("extension-chromium/manifest.json"),
    Path("pyproject.toml"),
)
VERSION_RE = re.compile(r"(?:0|[1-9]\d*)(?:\.(?:0|[1-9]\d*)){0,3}\Z")


def run(*args: str, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    if result.returncode != 0 or not capture_output:
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
    if result.returncode != 0:
        sys.exit(f"error: `{shlex.join(args)}` failed with exit status {result.returncode}")
    return result


def validate_version(value: str) -> str:
    version = value.removeprefix("v")
    if not VERSION_RE.fullmatch(version):
        raise ValueError(
            "version must contain one to four dot-separated integers (for example 0.3.0)"
        )
    parts = [int(part) for part in version.split(".")]
    if not any(parts) or any(part > 65535 for part in parts):
        raise ValueError("version components must be 0-65535 and the version cannot be all zero")
    return version


def update_versions(version: str) -> None:
    for relative in VERSION_FILES[:2]:
        path = ROOT / relative
        manifest = json.loads(path.read_text())
        manifest["version"] = version
        path.write_text(json.dumps(manifest, indent=2) + "\n")

    pyproject = ROOT / VERSION_FILES[2]
    contents, replacements = re.subn(
        r'(?m)^version = "[^"]+"$', f'version = "{version}"', pyproject.read_text(), count=1
    )
    if replacements != 1:
        raise RuntimeError("could not find the project version in pyproject.toml")
    pyproject.write_text(contents)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="release version, with or without a leading v")
    args = parser.parse_args()
    try:
        version = validate_version(args.version)
    except ValueError as error:
        parser.error(str(error))
    tag = f"v{version}"

    if run("git", "status", "--porcelain", capture_output=True).stdout:
        print("error: release preparation requires a clean worktree", file=sys.stderr)
        return 1
    if (
        subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/tags/{tag}"], cwd=ROOT
        ).returncode
        == 0
    ):
        print(f"error: local tag {tag} already exists", file=sys.stderr)
        return 1

    update_versions(version)
    run("just", "check-version", tag)
    # uv.lock records the project version; left stale, the commit's `uv run` hooks rewrite it
    # mid-commit and pre-commit aborts.
    run("uv", "lock")
    run("git", "add", "uv.lock", *(str(path) for path in VERSION_FILES))
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode == 0:
        print(f"Nothing to commit for new {version} version.")
    else:
        run("git", "commit", "-m", f"Bump version to {version}")

    # do git-tag.
    run("git", "tag", tag)
    print(f"Prepared {tag}. Publish it with: git push origin HEAD {tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
