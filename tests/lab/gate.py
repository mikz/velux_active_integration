"""Hold application startup until host inspection proves the private network."""

import hashlib
import os
import shutil
import sys
import time
from pathlib import Path


def main():
    role, *command = sys.argv[1:]
    if role not in {"ha", "simulator", "runner"} or not command:
        raise SystemExit("Invalid lab gate invocation")
    gate = Path("/control") / f"start-{role}"
    deadline = time.monotonic() + 180
    while not gate.exists():
        if time.monotonic() > deadline:
            raise SystemExit("Host did not release isolation gate")
        time.sleep(0.1)
    if gate.read_text().strip() != os.environ["LAB_RUN_ID"]:
        raise SystemExit("Isolation gate belongs to a different run")
    if role == "ha":
        config = Path("/config")
        config.mkdir(exist_ok=True)
        archive = Path("/opt/velux-active/velux_active.zip")
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        receipt = config / ".lab-artifact-sha256"
        if receipt.exists() and receipt.read_text().strip() != digest:
            raise SystemExit("Persistent configuration contains another release")
        if not receipt.exists():
            configuration = (
                Path("/lab/configuration.yaml")
                .read_text()
                .replace("LAB_HA_ADDRESS", os.environ["LAB_HA_ADDRESS"])
            )
            (config / "configuration.yaml").write_text(configuration)
            for filename, initial in (
                ("automations.yaml", "[]\n"),
                ("scripts.yaml", "{}\n"),
                ("scenes.yaml", "[]\n"),
            ):
                (config / filename).write_text(initial)
            target = config / "custom_components"
            target.mkdir(exist_ok=True)
            shutil.copytree("/opt/velux-active/integration", target / "velux_active")
            receipt.write_text(digest + "\n")
    os.execvp(command[0], command)


if __name__ == "__main__":
    main()
