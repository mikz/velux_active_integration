"""Exact-deadline installed fixtures must start through an integer native epoch."""

from homeassistant.helpers import device_registry as dr

from custom_components.velux_active import async_remove_config_entry_device
from tests.integration.test_quality import loaded as loaded
from tests.integration.test_quality import refresh
from tests.lab.cloud import HOME
from tests.lab.probe import logical_time, native_integer_clock_baseline


async def test_native_integer_epoch_prevents_fractional_topology_veto_oracle_failure(hass, loaded):
    entry, simulator, _ = loaded
    fractional = 147.42818356355824
    assert fractional + 900 < (fractional + 600) + 300
    with logical_time(fractional):
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
    clock, coordinator = await native_integer_clock_baseline(hass, entry)
    assert clock == 148.0
    assert coordinator.topology_attempted_at == coordinator.topology_observed_at == clock
    device = dr.async_get(hass).async_get_device_by_identifier(
        ("velux_active", "lab-gateway"), entry.entry_id
    )
    with logical_time(clock + 300):
        await refresh(hass)
    simulator.state["topology_outage"] = 503
    before = len(simulator.requests)
    with logical_time(clock + 600):
        await refresh(hass)
        assert simulator.requests[before:] == [("/api/homesdata", None), ("/api/homestatus", HOME)]
        assert coordinator.topology_attempted_at == clock + 600
        assert coordinator.topology_observed_at == clock + 300 and coordinator.topology_failed
    simulator.state["topology_outage"] = 0
    simulator.state["topology_payload"] = {"body": {"homes": [{"id": HOME, "modules": []}]}}
    simulator.state["status_payload"] = {
        "body": {"home": {"modules": [{"id": "lab-gateway", "type": "FUTURE"}]}}
    }
    before = len(simulator.requests)
    with logical_time(clock + 900):
        await refresh(hass)
        assert simulator.requests[before:] == [("/api/homesdata", None), ("/api/homestatus", HOME)]
        assert coordinator.topology_attempted_at == coordinator.topology_observed_at == clock + 900
        assert not coordinator.topology_failed and "lab-gateway" in coordinator.api.status_presence
        assert not await async_remove_config_entry_device(hass, entry, device)
    simulator.state["status_payload"] = {"body": {"home": {"modules": []}}}
    before = len(simulator.requests)
    with logical_time(clock + 960):
        await refresh(hass)
        assert simulator.requests[before:] == [("/api/homestatus", HOME)]
        assert coordinator.topology_attempted_at == coordinator.topology_observed_at == clock + 900
        assert "lab-gateway" in coordinator.api.status_presence
        assert not await async_remove_config_entry_device(hass, entry, device)
    before = len(simulator.requests)
    with logical_time(clock + 1200):
        # Prior absence evidence expires at the exact boundary before the next request.
        assert not await async_remove_config_entry_device(hass, entry, device)
        await refresh(hass)
        assert simulator.requests[before:] == [("/api/homesdata", None), ("/api/homestatus", HOME)]
        assert coordinator.topology_attempted_at == coordinator.topology_observed_at == clock + 1200
        assert not coordinator.api.status_presence
        assert await async_remove_config_entry_device(hass, entry, device)
