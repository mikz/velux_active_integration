"""Enable custom integrations only in the local test Home Assistant."""

import pytest


@pytest.fixture(autouse=True)
def _custom_integrations(enable_custom_integrations):
    """Load this integration in the HA test instance."""


@pytest.fixture
async def cloud(aiohttp_server, socket_enabled):
    """Expose only the synthetic service on the test HTTP boundary."""
    import aiohttp

    from custom_components.velux_active.api import VeluxActiveAPI
    from tests.lab.cloud import Cloud

    simulator = Cloud()
    server = await aiohttp_server(simulator.app())
    async with aiohttp.ClientSession() as session:
        yield simulator, VeluxActiveAPI(session, base_url=str(server.make_url("")))


@pytest.fixture(scope="session")
def artifact_runtime(tmp_path_factory):
    """Prepare a clean aiohttp-only interpreter for bundled ZIP smoke tests."""
    import subprocess
    import sys
    from pathlib import Path

    from scripts.release import ROOT

    directory = tmp_path_factory.mktemp("client-artifact")
    environment = directory / "venv"
    subprocess.run(
        ["uv", "venv", "--python", sys.executable, str(environment)],
        check=True,
        capture_output=True,
    )
    interpreter = environment / "bin/python"
    wheelhouse = ROOT / ".lab/runtime-wheelhouse"
    if not (wheelhouse / "receipt.json").is_file():
        raise RuntimeError("Run scripts/prepare_runtime_artifacts.py before artifact tests")
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--no-index",
            "--find-links",
            str(wheelhouse),
            "--python",
            str(interpreter),
            "--requirement",
            str(wheelhouse / "requirements.txt"),
        ],
        check=True,
        capture_output=True,
    )
    assert Path(interpreter).exists()
    return interpreter
