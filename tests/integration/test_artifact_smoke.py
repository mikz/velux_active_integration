"""Synthetic proof that the smoke runner executes extracted ZIP code, never checkout code."""

import asyncio
import hashlib
import json
import sys
import zipfile
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.velux_active.api import VeluxActiveAPI
from scripts import release
from scripts.cloud_smoke import check, extract_verified
from tests.lab.cloud import PASSWORD, USERNAME


async def test_artifact_smoke_runs_isolated_zip_members_and_hides_credentials(
    tmp_path, cloud, client_artifact_runtime
):
    _, api = cloud
    interpreter, wheel = client_artifact_runtime
    credentials = tmp_path / "credentials.json"
    credentials.write_text(json.dumps({"username": USERNAME, "password": PASSWORD}))
    archive = tmp_path / "integration.zip"
    with zipfile.ZipFile(archive, "w") as payload:
        for name, value in release.files().items():
            payload.writestr(name, value)
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "scripts/cloud_smoke.py",
        "--archive",
        str(archive),
        "--credentials",
        str(credentials),
        "--python",
        str(interpreter),
        "--dependency-wheel",
        str(wheel),
        "--synthetic-url",
        api._base_url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    assert PASSWORD.encode() not in stdout + stderr
    assert USERNAME.encode() not in stdout + stderr
    report = json.loads(stdout)
    assert process.returncode == 0, report
    assert report["isolated"] and report["status"] == "passed"
    assert report["authenticated"] and report["token_refreshed"] and report["status_refreshed"]
    assert report["parsed_device_count"] == report["refreshed_module_count"] == 4
    dependency = report["dependency_proof"]
    assert dependency["version"] == "0.1.0"
    assert VeluxActiveAPI.__module__ in dependency["modules"]
    assert dependency["wheel_sha256"] == hashlib.sha256(wheel.read_bytes()).hexdigest()
    with zipfile.ZipFile(wheel) as payload:
        for origin in dependency["modules"].values():
            assert origin["sha256"] == hashlib.sha256(payload.read(origin["member"])).hexdigest()
    assert (
        report["zip_sha256"]
        == hashlib.sha256(await asyncio.to_thread(archive.read_bytes)).hexdigest()
    )
    with zipfile.ZipFile(archive) as payload:
        for origin in report["artifact_modules"].values():
            assert origin["sha256"] == hashlib.sha256(payload.read(origin["member"])).hexdigest()


async def test_smoke_empty_inventory_cannot_claim_status_proof():
    api = SimpleNamespace(authenticate=AsyncMock(), get_home_data=AsyncMock(return_value=[]))
    with pytest.raises(ValueError, match="nonempty inventory"):
        await check(
            SimpleNamespace(VeluxActiveAPI=lambda session: api),
            {"username": USERNAME, "password": PASSWORD},
            None,
        )


@pytest.mark.parametrize("name", ["../escape.py", "/absolute.py"])
def test_smoke_rejects_unsafe_zip_members(tmp_path, name):
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as payload:
        payload.writestr(name, "pass")
    with pytest.raises(ValueError):
        extract_verified(archive, tmp_path / "extracted")


@pytest.mark.parametrize("kind", ["editable", "wrong_wheel_version"])
async def test_smoke_rejects_source_fallback_or_wrong_wheel_before_cloud_io(
    tmp_path, cloud, client_artifact_runtime, kind
):
    simulator, api = cloud
    interpreter, wheel = client_artifact_runtime
    credentials = tmp_path / "credentials.json"
    credentials.write_text(json.dumps({"username": USERNAME, "password": PASSWORD}))
    archive = tmp_path / "integration.zip"
    with zipfile.ZipFile(archive, "w") as payload:
        for name, value in release.files().items():
            payload.writestr(name, value)
    if kind == "editable":
        interpreter = sys.executable
    else:
        altered = tmp_path / "different-version.whl"
        with zipfile.ZipFile(wheel) as source, zipfile.ZipFile(altered, "w") as destination:
            for name in source.namelist():
                data = source.read(name)
                if name.endswith(".dist-info/METADATA"):
                    data = data.replace(b"Version: 0.1.0", b"Version: 0.1.1")
                destination.writestr(name, data)
        wheel = altered
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "scripts/cloud_smoke.py",
        "--archive",
        str(archive),
        "--credentials",
        str(credentials),
        "--python",
        str(interpreter),
        "--dependency-wheel",
        str(wheel),
        "--synthetic-url",
        api._base_url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    assert PASSWORD.encode() not in stdout + stderr
    assert USERNAME.encode() not in stdout + stderr
    assert process.returncode == 1
    assert json.loads(stdout) == {"status": "failed", "error_type": "ValueError"}
    assert simulator.counts["password"] == 0
    assert simulator.counts["homesdata"] == simulator.counts["homestatus"] == 0
