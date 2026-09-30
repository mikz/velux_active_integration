"""Exercise the real HTTP boundary with synthetic cloud responses."""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.velux_active.api import (
    APIConnectionError,
    InvalidAuthError,
    RateLimitError,
    device_from_module,
)
from tests.lab.cloud import PASSWORD, USERNAME


async def test_modern_topology_merges_metadata_and_accepts_sparse_status(cloud):
    simulator, api = cloud
    await api.authenticate(USERNAME, PASSWORD)
    homes = await api.get_home_data()
    devices = [device_from_module(m) for m in await api.get_home_statuses(homes[0])]
    assert len(devices) == 4
    assert devices[0].is_raining is False
    assert devices[1].current_position == 7
    assert devices[0].firmware_revision_netatmo is None
    simulator.state["omit_rain"] = True
    devices = [device_from_module(m) for m in await api.get_home_statuses(homes[0])]
    assert devices[0].is_raining is None


async def test_refresh_rotation_and_revocation_recover_without_recreating_entry(cloud):
    simulator, api = cloud
    await api.authenticate(USERNAME, PASSWORD)
    api.auth_token.expires_at = datetime.now() + timedelta(seconds=5)
    await api.get_home_data()
    assert simulator.counts["refresh_token"] == 1
    assert simulator.counts["password"] == 1
    simulator.access.clear()
    simulator.refresh.clear()
    await api.get_home_data()
    assert simulator.counts["refresh_token"] == 2
    assert simulator.counts["password"] == 2


@pytest.mark.parametrize(
    "status,error", [(503, APIConnectionError), (429, RateLimitError), (403, RateLimitError)]
)
async def test_outages_and_throttling_do_not_trigger_password_logins(cloud, status, error):
    simulator, api = cloud
    await api.authenticate(USERNAME, PASSWORD)
    simulator.state["outage"] = status
    with pytest.raises(error):
        await api.get_home_data()
    assert simulator.counts["password"] == 1
    assert simulator.counts["refresh_token"] == 0


async def test_invalid_password_and_token_repr_do_not_leak_secrets(cloud):
    _, api = cloud
    with pytest.raises(InvalidAuthError, match="rejected authentication"):
        await api.authenticate(USERNAME, "wrong")
    token = await api.authenticate(USERNAME, PASSWORD)
    assert token.access_token not in str(token)
    assert token.refresh_token not in repr(token)


async def test_native_ha_setup_rain_outage_reload_and_reauth(hass, cloud):
    simulator, api = cloud
    entry = MockConfigEntry(
        domain="velux_active",
        title="Velux Active",
        version=1,
        data={"username": USERNAME, "password": PASSWORD},
    )
    entry.add_to_hass(hass)
    er.async_get(hass).async_get_or_create(
        "binary_sensor",
        "velux_active",
        "lab-gateway_is_raining",
        config_entry=entry,
        suggested_object_id="gateway_lab_gateway_is_raining",
    )
    with patch("custom_components.velux_active.coordinator.VeluxActiveAPI", return_value=api):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        rain = "binary_sensor.gateway_lab_gateway_is_raining"
        assert hass.states.get(rain).state == "off"
        simulator.state["rain"] = True
        await entry.runtime_data.async_refresh()
        assert hass.states.get(rain).state == "on"
        simulator.state["outage"] = 503
        await entry.runtime_data.async_refresh()
        assert hass.states.get(rain).state == "unavailable"
        simulator.state["outage"] = 0
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get(rain).state == "on"
        simulator.access.clear()
        simulator.refresh.clear()
        simulator.state["password"] = "changed-lab-password"
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        flows = hass.config_entries.flow.async_progress_by_handler("velux_active")
        assert len(flows) == 1
        assert flows[0]["context"]["source"] == "reauth"
        with patch("custom_components.velux_active.config_flow.VeluxActiveAPI", return_value=api):
            result = await hass.config_entries.flow.async_configure(
                flows[0]["flow_id"], {"username": USERNAME, "password": "changed-lab-password"}
            )
        assert result["reason"] == "reauth_successful"
        await hass.async_block_till_done()
        assert entry.data["password"] == "changed-lab-password"
        assert hass.states.get(rain).state == "on"
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert hass.services.has_service("velux_active", "refresh")


async def test_native_user_flow_distinguishes_authentication_from_outage(hass, cloud):
    simulator, api = cloud
    with (
        patch("custom_components.velux_active.config_flow.VeluxActiveAPI", return_value=api),
        patch("custom_components.velux_active.coordinator.VeluxActiveAPI", return_value=api),
    ):
        flow = await hass.config_entries.flow.async_init("velux_active", context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], {"username": USERNAME, "password": "wrong"}
        )
        assert result["errors"] == {"base": "invalid_auth"}
        simulator.state["outage"] = 503
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], {"username": USERNAME, "password": PASSWORD}
        )
        assert result["errors"] == {"base": "cannot_connect"}
        simulator.state["outage"] = 0
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], {"username": USERNAME, "password": PASSWORD}
        )
        assert result["type"] == "create_entry"
        await hass.async_block_till_done()
        assert await hass.config_entries.async_unload(result["result"].entry_id)
