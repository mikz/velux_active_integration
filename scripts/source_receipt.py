#!/usr/bin/env python3
"""Publish only explicit source gate outcomes, coverage and verified artifact facts."""

import argparse
import hashlib
import importlib.metadata
import json
import subprocess
import sys
import zipfile
from pathlib import Path

from scripts.check_coverage import validate as validate_coverage

GATES = {
    "sync": "uv sync --locked",
    "prepare": "uv run python scripts/prepare_runtime_artifacts.py",
    "ruff": "uv run ruff check .",
    "format": "uv run ruff format --check .",
    "pytest": (
        "uv run pytest --cov=custom_components.velux_active "
        "--cov-branch --cov-report=term-missing "
        "--cov-report=json:artifacts/source-coverage.json"
    ),
    "coverage": "uv run python scripts/check_coverage.py artifacts/source-coverage.json",
    "mypy": "uv run mypy",
    "build": "uv run python scripts/release.py build",
    "verify": "uv run python scripts/release.py verify",
}


def artifact_proof(root):
    """Compare the self-contained archive against the independent tracked inventory."""
    prefix = "custom_components/velux_active/"
    tracked = subprocess.check_output(["git", "ls-files", "-z", "--", prefix], cwd=root)
    expected = {
        name.removeprefix(prefix): (root / name).read_bytes()
        for name in tracked.decode().split("\0")
        if name
    }
    archive = root / "dist/velux_active.zip"
    with zipfile.ZipFile(archive) as package:
        if sorted(package.namelist()) != sorted(expected) or any(
            package.read(name) != data for name, data in expected.items()
        ):
            raise ValueError("Integration archive inventory or bytes mismatch")
    manifest = json.loads(expected["manifest.json"])
    if manifest["requirements"]:
        raise ValueError("The integration must include its client")
    return {
        "integration": {
            "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "version": manifest["version"],
            "member_hashes": {
                name: hashlib.sha256(data).hexdigest() for name, data in expected.items()
            },
        },
        "bundled_client": True,
    }


def collect(root, outcomes):
    if set(outcomes) != set(GATES) or any(
        value not in {"success", "failure", "skipped", "cancelled"} for value in outcomes.values()
    ):
        raise ValueError("Expected only explicit known gate outcomes")
    receipt = {
        "source_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "gates": {
            key: {"command": command, "outcome": outcomes[key]} for key, command in GATES.items()
        },
        "tools": {"python": sys.version.split()[0]},
        "coverage_validation": "unavailable",
        "artifact_validation": "unavailable",
    }
    for tool in (
        "pytest",
        "pytest-homeassistant-custom-component",
        "homeassistant",
        "coverage",
        "mypy",
        "ruff",
        "aiohttp",
    ):
        try:
            receipt["tools"][tool] = importlib.metadata.version(tool)
        except importlib.metadata.PackageNotFoundError:
            receipt["tools"][tool] = "unavailable"
    coverage = root / "artifacts/source-coverage.json"
    if coverage.exists() and outcomes["pytest"] in {"success", "failure"}:
        try:
            report = json.loads(coverage.read_text())
            failures = validate_coverage(report, root)
            receipt["coverage_validation"] = "failed" if failures else "passed"
            receipt["coverage"] = {
                "branch_coverage": report["meta"]["branch_coverage"],
                "modules": {
                    name: value["summary"]
                    for name, value in report["files"].items()
                    if name.startswith(("custom_components/velux_active/",))
                },
            }
        except KeyError, ValueError, TypeError:
            receipt["coverage_validation"] = "failed"
    if all(outcomes[key] == "success" for key in ("prepare", "build", "verify")):
        try:
            receipt["artifacts"] = artifact_proof(root)
            receipt["artifact_validation"] = "passed"
        except ValueError, KeyError, OSError, zipfile.BadZipFile:
            receipt["artifact_validation"] = "failed"
    receipt["status"] = (
        "passed"
        if (
            all(value == "success" for value in outcomes.values())
            and receipt["coverage_validation"] == receipt["artifact_validation"] == "passed"
        )
        else "not_passed"
    )
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outcomes", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    receipt = collect(root, json.loads(args.outcomes))
    target = root / "artifacts/source-receipt.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    if receipt["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
