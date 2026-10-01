#!/usr/bin/env python3
"""Check package tags independently from integration release tags."""

import hashlib
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate_tag(version: str, tag: str) -> None:
    """Only the exact separately versioned client tag may publish these bytes."""
    if tag != f"client-v{version}":
        raise ValueError("Tag does not match the prepared client package version")


def validate_wheel(wheel: Path, root: Path = ROOT) -> dict[str, str]:
    """Compare payload with independently tracked source, not the builder's file glob."""
    source = "packages/velux-active-client/src/"
    tracked = subprocess.check_output(["git", "ls-files", "-z", "--", source], cwd=root)
    expected = {
        path[len(source) :]: (root / path).read_bytes()
        for path in tracked.decode().split("\0")
        if path
    }
    if not expected:
        raise ValueError("Client source inventory has not been tracked")
    with zipfile.ZipFile(wheel) as package:
        names = package.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate wheel member")
        actual = {name for name in names if name.startswith("velux_active_client/")}
        if actual != set(expected):
            raise ValueError("Wheel does not match tracked client payload inventory")
        if any(package.read(name) != data for name, data in expected.items()):
            raise ValueError("Wheel differs from tracked client source bytes")
    return {name: hashlib.sha256(data).hexdigest() for name, data in expected.items()}


if __name__ == "__main__":
    project = tomllib.loads((ROOT / "packages/velux-active-client/pyproject.toml").read_text())
    validate_tag(project["project"]["version"], sys.argv[1])
