"""Hold application startup until host inspection proves the private network."""

import hashlib
import importlib
import importlib.metadata
import json
import os
import platform
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
        from cloud_smoke import verify_dependency

        importlib.import_module("velux_active_client")
        manifest = json.loads(Path("/opt/velux-active/integration/manifest.json").read_text())
        wheels = list(Path("/opt/velux-active").glob("*.whl"))
        if len(wheels) != 1:
            raise SystemExit("Lab requires exactly one frozen client wheel")
        proof = verify_dependency(wheels[0], manifest["requirements"])
        if proof["wheel_sha256"] != os.environ["LAB_CLIENT_WHEEL_SHA256"]:
            raise SystemExit("Installed wheel does not match the frozen lab receipt")
        proof.update(
            python_version=platform.python_version(),
            aiohttp_version=importlib.metadata.version("aiohttp"),
            homeassistant_version=importlib.metadata.version("homeassistant"),
            scope="local validation candidate; requires the matching local wheel",
        )
        (Path("/control") / "client-proof.json").write_text(json.dumps(proof))
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
            shutil.copytree("/lab/probe", target / "lab_probe")
            # A real version-one entry/registry exists BEFORE candidate first setup.
            storage = config / ".storage"
            storage.mkdir(exist_ok=True)
            from legacy import with_composite

            fixtures = with_composite(json.loads(Path("/lab/legacy_storage.json").read_text()))
            for key, payload in fixtures.items():
                (storage / key).write_text(json.dumps(payload) + "\n")
            shutil.copyfile("/lab/legacy-recorder.db", config / "home-assistant_v2.db")
            receipt.write_text(digest + "\n")
    os.execvp(command[0], command)


if __name__ == "__main__":
    main()
