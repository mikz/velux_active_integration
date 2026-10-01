"""Callback privacy and native entry-bound reauth repair lifecycle."""

import json
from unittest.mock import patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir

from custom_components.velux_active.diagnostics import (
    async_get_config_entry_diagnostics,
    observation_age,
)
from tests.integration.test_quality import loaded as loaded
from tests.integration.test_quality import refresh
from tests.lab.cloud import USERNAME


async def test_diagnostics_allowlist_omits_provider_credentials_names_and_errors(hass, loaded):
    entry, _, _ = loaded
    sentinel = "PRIVATE_PROVIDER_SENTINEL"
    hass.config_entries.async_update_entry(
        entry,
        title=sentinel,
        data={"username": sentinel, "password": sentinel, "nested": {"token": sentinel}},
    )
    coordinator = entry.runtime_data
    for home in coordinator.data.values():
        for device in home["devices"]:
            device.type = sentinel
            if hasattr(device, "name"):
                device.name = sentinel
    coordinator.last_exception = Exception(sentinel)
    coordinator.topology_observed_at = float("nan")
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert sentinel not in json.dumps(result, allow_nan=False)
    assert set(result) == {
        "loaded",
        "schema_version",
        "status_success",
        "topology_initialized",
        "topology_failed",
        "refresh_in_progress",
        "home_count",
        "inventory_count",
        "supported_model_counts",
        "topology_age_seconds",
        "status_age_seconds",
        "topology_attempt_age_seconds",
        "status_interval_seconds",
        "topology_interval_seconds",
    }
    assert result["supported_model_counts"] == {
        "gateway": 0,
        "window": 0,
        "shutter": 0,
        "sensor": 0,
    }
    assert result["topology_age_seconds"] is None


async def test_diagnostics_known_counts_and_unloaded_entry(hass, loaded):
    entry, _, _ = loaded
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["supported_model_counts"] == {
        "gateway": 1,
        "window": 1,
        "shutter": 1,
        "sensor": 1,
    }
    assert result["inventory_count"] == 4 and result["home_count"] == 1
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await async_get_config_entry_diagnostics(hass, entry) == {
        "loaded": False,
        "schema_version": 1,
    }


@pytest.mark.parametrize(
    "observed,now,expected",
    [
        (None, 10, None),
        (float("inf"), 10, None),
        (10, 9, None),
        (10, float("inf"), None),
        (9, 10.123456, 1.123),
    ],
)
def test_diagnostic_timing_is_finite_relative_and_bounded(observed, now, expected):
    with patch("custom_components.velux_active.diagnostics.monotonic", return_value=now):
        assert observation_age(observed) == expected


@pytest.mark.parametrize("resolve", ["reauth", "remove"])
async def test_native_reauth_repair_is_entry_bound_deduplicated_and_cleans_up(
    hass, loaded, resolve
):
    entry, simulator, api = loaded
    simulator.access.clear()
    simulator.refresh.clear()
    simulator.state["password"] = "renewed-synthetic-password"
    for _ in range(2):
        with pytest.raises(HomeAssistantError):
            await refresh(hass)
        await hass.async_block_till_done()
    issue_id = f"config_entry_reauth_velux_active_{entry.entry_id}"
    registry = ir.async_get(hass)
    matching = [
        issue
        for (domain, identifier), issue in registry.issues.items()
        if domain == "homeassistant" and identifier == issue_id
    ]
    assert len(matching) == 1 and matching[0].issue_domain == "velux_active"
    flows = hass.config_entries.flow.async_progress_by_handler("velux_active")
    assert len(flows) == 1 and flows[0]["context"]["entry_id"] == entry.entry_id
    assert matching[0].data["flow_id"] == flows[0]["flow_id"]
    if resolve == "reauth":
        with patch("custom_components.velux_active.config_flow.VeluxActiveAPI", return_value=api):
            result = await hass.config_entries.flow.async_configure(
                flows[0]["flow_id"],
                {"username": USERNAME, "password": "renewed-synthetic-password"},
            )
        assert result["reason"] == "reauth_successful"
        await hass.async_block_till_done()
    else:
        assert await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()
    assert ("homeassistant", issue_id) not in registry.issues
    assert not hass.config_entries.flow.async_progress_by_handler("velux_active")


async def test_native_diagnostics_response_scopes_owned_data_and_export_metadata(
    hass, loaded, hass_client
):
    from homeassistant.setup import async_setup_component

    entry, _, _ = loaded
    sentinel = "PRIVATE_ENTRY_TITLE_SENTINEL"
    hass.config_entries.async_update_entry(entry, title=sentinel)
    assert await async_setup_component(hass, "diagnostics", {})
    client = await hass_client()
    clock = max(entry.runtime_data.topology_observed_at, entry.runtime_data.status_observed_at) + 1
    with patch("custom_components.velux_active.diagnostics.monotonic", return_value=clock):
        response = await client.get(f"/api/diagnostics/config_entry/{entry.entry_id}")
        expected = await async_get_config_entry_diagnostics(hass, entry)
    assert response.status == 200
    assert response.content_type == "application/json"
    assert sentinel not in response.headers["Content-Disposition"]
    payload = await response.json()
    assert payload["data"] == expected
    assert sentinel not in json.dumps(payload["data"])
    assert "home_assistant" in payload and "integration_manifest" in payload


async def test_diagnostics_counts_supported_nxd_and_omits_unknown_type(hass, loaded):
    entry, _, _ = loaded
    for snapshot in entry.runtime_data.data.values():
        for device in snapshot["devices"]:
            if device.type == "NXS":
                device.type = "NXD"
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["supported_model_counts"]["sensor"] == 1
    for snapshot in entry.runtime_data.data.values():
        for device in snapshot["devices"]:
            if device.type == "NXD":
                device.type = "PRIVATE_UNKNOWN_MODEL"
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["supported_model_counts"]["sensor"] == 0
    assert "PRIVATE_UNKNOWN_MODEL" not in json.dumps(result)
