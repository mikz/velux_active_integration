#!/usr/bin/env python3
"""Prepare local typed distributions and an explicit locked runtime wheelhouse.

Network access is confined to this preparation phase. Artifact execution uses
only the resulting local files; it never relies on an incidental uv index cache.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def prepare(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--no-isolation",
            str(ROOT / "packages/velux-active-client"),
            "--outdir",
            str(ROOT / "dist/client"),
        ],
        check=True,
    )
    requirements = output / "requirements.txt"
    subprocess.run(
        [
            "uv",
            "export",
            "--frozen",
            "--no-dev",
            "--no-emit-workspace",
            "--format",
            "requirements-txt",
            "--output-file",
            str(requirements),
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "download",
            "--require-hashes",
            "--only-binary=:all:",
            "--no-deps",
            "--index-url",
            "https://pypi.org/simple",
            "--requirement",
            str(requirements),
            "--dest",
            str(output),
        ],
        check=True,
    )
    receipt = {
        "uv_lock_sha256": hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest(),
        "runtime_wheels": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.glob("*.whl"))
        },
        "local_client_distributions": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / "dist/client").glob("*"))
            if p.name.endswith((".whl", ".tar.gz"))
        },
        "scope": "local validation candidate; requires the matching local wheel",
    }
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".lab/client-wheelhouse")
    prepare(parser.parse_args().output)
