"""Full cloud deadlines survive native retries without retaining client identity."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import aiohttp_client
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.velux_active.api import VeluxActiveAPI
from custom_components.velux_active.const import DOMAIN, async_rate_limit_state
from tests.lab.cloud import PASSWORD, USERNAME, Cloud


@pytest.fixture
async def native_clients(hass, aiohttp_server, socket_enabled):
    simulator = Cloud()
    server = await aiohttp_server(simulator.app())
    clients = []

    def factory(session, *, rate_limit_state):
        client = VeluxActiveAPI(
            session, base_url=str(server.make_url("")), rate_limit_state=rate_limit_state
        )
        clients.append(client)
        return client

    with (
        patch("custom_components.velux_active.coordinator.VeluxActiveAPI", side_effect=factory),
        patch("custom_components.velux_active.config_flow.VeluxActiveAPI", side_effect=factory),
    ):
        yield simulator, clients


@pytest.mark.parametrize("endpoint", ["auth", "topology"])
async def test_native_setup_retry_preserves_cloud_deadline_and_fresh_credentials(
    hass, native_clients, endpoint
):
    simulator, clients = native_clients
    simulator.state["retry_after"] = "99999"
    if endpoint == "auth":
        simulator.state["outage"] = 429
    else:
        simulator.state["topology_outage"] = 429
    entry = MockConfigEntry(domain=DOMAIN, data={"username": USERNAME, "password": PASSWORD})
    entry.add_to_hass(hass)
    now = dt_util.utcnow()
    with patch("velux_active_client.client.monotonic", return_value=1000):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.SETUP_RETRY
        initial_calls = list(simulator.requests)
        deadline = async_rate_limit_state(hass).deadline
    # Advance native retry and client elapsed time together inside the deadline.
    with patch("velux_active_client.client.monotonic", return_value=1006):
        async_fire_time_changed(hass, now + timedelta(seconds=6))
        await hass.async_block_till_done(wait_background_tasks=True)
        assert entry.state is ConfigEntryState.SETUP_RETRY
        assert simulator.requests == initial_calls
        assert len(clients) == 2 and clients[0] is not clients[1]
        assert clients[1].auth_token is None
        assert async_rate_limit_state(hass).deadline == deadline
    simulator.state["outage"] = 0
    simulator.state.pop("topology_outage", None)
    simulator.state["password"] = "replacement-password"
    hass.config_entries.async_update_entry(
        entry, data={"username": USERNAME, "password": "replacement-password"}
    )
    with patch("velux_active_client.client.monotonic", return_value=100999):
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        assert len(clients) == 3
        assert clients[2].auth_token is not None
        assert not aiohttp_client.async_get_clientsession(hass).closed
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert not aiohttp_client.async_get_clientsession(hass).closed


async def test_flow_before_setup_and_entry_removal_share_only_deadline(hass, native_clients):
    simulator, clients = native_clients
    simulator.state["outage"] = 429
    with patch("velux_active_client.client.monotonic", return_value=1000):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data={"username": USERNAME, "password": PASSWORD}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}
        state = async_rate_limit_state(hass)
        calls = list(simulator.requests)
        hass.config_entries.flow.async_abort(result["flow_id"])
    entry = MockConfigEntry(
        domain=DOMAIN, data={"username": "another@example.invalid", "password": "another-password"}
    )
    entry.add_to_hass(hass)
    with patch("velux_active_client.client.monotonic", return_value=1001):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert async_rate_limit_state(hass) is state
        assert simulator.requests == calls
        assert clients[-1].auth_token is None
        assert await hass.config_entries.async_remove(entry.entry_id)
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data={"username": USERNAME, "password": "new-password"},
        )
        assert result["errors"] == {"base": "cannot_connect"}
        assert simulator.requests == calls
        assert async_rate_limit_state(hass) is state
        assert clients[-1].auth_token is None
        hass.config_entries.flow.async_abort(result["flow_id"])


async def test_loaded_reload_and_blocked_reconfigure_preserve_credentials(hass, native_clients):
    from homeassistant.exceptions import HomeAssistantError

    from tests.integration.test_quality import refresh

    simulator, clients = native_clients
    entry = MockConfigEntry(domain=DOMAIN, data={"username": USERNAME, "password": PASSWORD})
    entry.add_to_hass(hass)
    with patch("velux_active_client.client.monotonic", return_value=1000):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        simulator.state.update(outage=429, retry_after="99999")
        with pytest.raises(HomeAssistantError):
            await refresh(hass)
        initial_calls = list(simulator.requests)
        state = async_rate_limit_state(hass)
    with patch("velux_active_client.client.monotonic", return_value=4601):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": USERNAME, "password": "unvalidated-new-password"}
        )
        assert result["errors"] == {"base": "cannot_connect"}
        assert entry.data == {"username": USERNAME, "password": PASSWORD}
        hass.config_entries.flow.async_abort(result["flow_id"])
        assert not await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.SETUP_RETRY
        assert async_rate_limit_state(hass) is state
        assert simulator.requests == initial_calls
        assert clients[-1].auth_token is None
        assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)
