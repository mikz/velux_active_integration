"""Installed scenarios must wait for Core, not just the config entry."""

from unittest.mock import AsyncMock

import pytest

from tests.lab.runner import Lab


@pytest.mark.parametrize("state", ["NOT_RUNNING", "STARTING", "RUNNING"])
async def test_loaded_entry_cannot_start_scenarios_before_core(monkeypatch, state):
    monkeypatch.setenv("LAB_HA_URL", "http://synthetic.invalid")
    monkeypatch.setenv("LAB_SIM_URL", "http://simulator.invalid")
    lab = Lab(None)
    lab.entry = "synthetic"
    lab.request = AsyncMock(return_value={"state": state})
    lab.ws = AsyncMock(return_value=[{"entry_id": "synthetic", "state": "loaded"}])
    assert await lab.loaded() is (state == "RUNNING")
    if state != "RUNNING":
        lab.ws.assert_not_awaited()
