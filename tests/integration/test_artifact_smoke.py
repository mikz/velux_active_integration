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


async def test_artifact_smoke_runs_isolated_zip_members_and_hides_credentials(tmp_path, cloud):
    _, api = cloud
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
    assert VeluxActiveAPI.__module__ in report["artifact_modules"]
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
