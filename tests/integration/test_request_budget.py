"""Actual incoming HTTP requests, including rejected requests, define the budget."""

import asyncio
from collections import Counter
from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.velux_active.api import RateLimitError
from custom_components.velux_active.const import DOMAIN
from tests.integration.test_quality import refresh
from tests.lab.cloud import PASSWORD, USERNAME


@pytest.fixture
async def two_homes(hass, cloud):
    simulator, api = cloud
    homes = ["first-synthetic-home", "second-synthetic-home"]
    simulator.state["topology_payload"] = {
        "body": {
            "homes": [
                {"id": home, "modules": [{"id": f"gateway-{index}", "type": "NXG"}]}
                for index, home in enumerate(homes)
            ]
        }
    }
    simulator.state["status_by_home"] = {
        home: {
            "body": {
                "home": {
                    "modules": [{"id": f"gateway-{index}", "is_raining": False, "reachable": True}]
                }
            }
        }
        for index, home in enumerate(homes)
    }
    entry = MockConfigEntry(domain=DOMAIN, data={"username": USERNAME, "password": PASSWORD})
    entry.add_to_hass(hass)
    with patch("custom_components.velux_active.coordinator.VeluxActiveAPI", return_value=api):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield entry, simulator, api, homes


def counts(simulator):
    return Counter(simulator.requests)


@pytest.mark.parametrize("unsupported", [False, True])
async def test_account_wide_duplicate_status_fails_atomically_and_recovers(
    hass, two_homes, unsupported
):
    entry, simulator, api, homes = two_homes
    before = entry.runtime_data.data
    for index, home in enumerate(homes):
        simulator.state["status_by_home"][home] = {
            "body": {
                "home": {
                    "modules": [
                        {
                            "id": "gateway-0",
                            "type": "FUTURE" if unsupported else "NXG",
                            "is_raining": bool(index),
                            "reachable": True,
                        }
                    ]
                }
            }
        }
    with pytest.raises(HomeAssistantError):
        await refresh(hass)
    assert not entry.runtime_data.last_update_success
    assert entry.runtime_data.data is before
    assert "gateway-0" in api.status_presence
    assert not entry.runtime_data.async_can_remove_device("gateway-0")
    for index, home in enumerate(homes):
        simulator.state["status_by_home"][home]["body"]["home"]["modules"][0]["id"] = (
            f"gateway-{index}"
        )
    await refresh(hass)
    assert entry.runtime_data.last_update_success


async def test_multi_home_poll_topology_cadence_and_manual_coalescing_raw_http(hass, two_homes):
    entry, simulator, api, homes = two_homes
    assert simulator.requests == [
        ("/oauth2/token", "password"),
        ("/api/homesdata", None),
        *(("/api/homestatus", home) for home in homes),
    ]
    start = entry.runtime_data.topology_attempted_at
    now = dt_util.utcnow()
    with patch("custom_components.velux_active.coordinator.monotonic", return_value=start + 60):
        async_fire_time_changed(hass, now + timedelta(seconds=61))
        await hass.async_block_till_done(wait_background_tasks=True)
    assert counts(simulator) == Counter(
        {
            ("/oauth2/token", "password"): 1,
            ("/api/homesdata", None): 1,
            **{("/api/homestatus", home): 2 for home in homes},
        }
    )
    entered, release = asyncio.Event(), asyncio.Event()
    original = api.get_home_statuses

    async def delayed(home):
        entered.set()
        await release.wait()
        return await original(home)

    with patch.object(api, "get_home_statuses", side_effect=delayed):
        first = asyncio.create_task(refresh(hass))
        await entered.wait()
        second = asyncio.create_task(refresh(hass))
        await asyncio.sleep(0)
        release.set()
        await asyncio.gather(first, second)
    assert counts(simulator)[("/api/homesdata", None)] == 1
    assert all(counts(simulator)[("/api/homestatus", home)] == 3 for home in homes)
    simulator.state["topology_outage"] = 503
    for delta in (300, 360, 599, 600):
        with patch(
            "custom_components.velux_active.coordinator.monotonic", return_value=start + delta
        ):
            await refresh(hass)
    assert (
        counts(simulator)[("/api/homesdata", None)] == 3
    )  # setup + two attempts, including failures
    assert all(counts(simulator)[("/api/homestatus", home)] == 7 for home in homes)
    assert counts(simulator)[("/oauth2/token", "password")] == 1


async def test_multi_home_401_replay_password_fallback_and_global_429_raw_http(hass, two_homes):
    entry, simulator, api, homes = two_homes
    simulator.requests.clear()
    simulator.access.clear()
    await refresh(hass)
    assert simulator.requests == [
        ("/api/homestatus", homes[0]),
        ("/oauth2/token", "refresh_token"),
        *(("/api/homestatus", home) for home in homes),
    ]
    simulator.requests.clear()
    simulator.access.clear()
    simulator.state["reject_refresh"] = True
    await refresh(hass)
    assert simulator.requests == [
        ("/api/homestatus", homes[0]),
        ("/oauth2/token", "refresh_token"),
        ("/oauth2/token", "password"),
        *(("/api/homestatus", home) for home in homes),
    ]
    simulator.requests.clear()
    simulator.state["outage"] = 429
    with pytest.raises(HomeAssistantError):
        await refresh(hass)
    assert simulator.requests == [("/api/homestatus", homes[0])]
    for operation in (
        api.get_home_data(),
        api.get_home_statuses(next(iter(entry.runtime_data.data))),
        api.authenticate(USERNAME, PASSWORD),
        api.refresh_access_token(api.auth_token),
    ):
        with pytest.raises(RateLimitError):
            await operation
    with pytest.raises(HomeAssistantError):
        await refresh(hass)
    assert simulator.requests == [("/api/homestatus", homes[0])]
