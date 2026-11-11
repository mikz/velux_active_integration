#!/usr/bin/env python3
"""Prove the manifest dependency installs from PyPI and matches reviewed source."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from scripts.client_release import ROOT, validate_wheel


def check_public_client(directory: Path) -> dict:
    requirements = json.loads((ROOT / "custom_components/velux_active/manifest.json").read_text())[
        "requirements"
    ]
    python = directory / "venv/bin/python"
    subprocess.run([sys.executable, "-m", "venv", str(python.parent.parent)], check=True)
    pip = [str(python), "-I", "-m", "pip", "--isolated", "--disable-pip-version-check"]
    index = ["--no-cache-dir", "--index-url", "https://pypi.org/simple"]
    environment = {key: value for key, value in os.environ.items() if not key.startswith("PIP_")}
    environment["PIP_CONFIG_FILE"] = os.devnull
    subprocess.run(
        [
            *pip,
            "download",
            *index,
            "--no-deps",
            "--only-binary=:all:",
            "--dest",
            str(directory),
            *requirements,
        ],
        check=True,
        env=environment,
    )
    (wheel,) = directory.glob("*.whl")
    validate_wheel(wheel)
    subprocess.run([*pip, "install", *index, *requirements], check=True, env=environment)
    proof = subprocess.check_output(
        [
            str(python),
            "-I",
            "-c",
            "import json, runpy, sys; from pathlib import Path; import velux_active_client; "
            "verify = runpy.run_path(sys.argv[1])['verify_dependency']; "
            "print(json.dumps(verify(Path(sys.argv[2]), json.loads(sys.argv[3]))))",
            str(ROOT / "scripts/cloud_smoke.py"),
            str(wheel),
            json.dumps(requirements),
        ],
        text=True,
        cwd=directory,
    )
    return json.loads(proof)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="velux-public-client-") as temporary:
        proof = check_public_client(Path(temporary))
    receipt = ROOT / "artifacts/public-client.json"
    receipt.parent.mkdir(exist_ok=True)
    receipt.write_text(json.dumps(proof, indent=2) + "\n")
    print(f"Verified PyPI client {proof['version']}: {proof['wheel_sha256']}")


if __name__ == "__main__":
    main()
