"""Native HA behavior contracts for account identity and refresh lifecycle."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.velux_active import async_unload_entry
from custom_components.velux_active.api import APIConnectionError, InvalidAuthError
from tests.lab.cloud import PASSWORD, USERNAME


@pytest.fixture
async def loaded(hass, cloud):
    simulator, api = cloud
    entry = MockConfigEntry(
        domain="velux_active", version=1, data={"username": USERNAME, "password": PASSWORD}
    )
    entry.add_to_hass(hass)
    with patch("custom_components.velux_active.coordinator.VeluxActiveAPI", return_value=api):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield entry, simulator, api


async def refresh(hass):
    await hass.services.async_call("velux_active", "refresh", {}, blocking=True)


async def test_action_is_registered_without_entry_and_survives_unload(hass, loaded):
    entry, _, _ = loaded
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert hass.services.has_service("velux_active", "refresh")
    with pytest.raises(ServiceValidationError, match="No VELUX"):
        await refresh(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await refresh(hass)


async def test_action_awaits_completed_update_and_serializes_callers(hass, loaded):
    entry, simulator, api = loaded
    entered = asyncio.Event()
    release = asyncio.Event()
    original = api.get_home_statuses
    concurrent = 0
    maximum = 0

    async def delayed(home):
        nonlocal concurrent, maximum
        concurrent += 1
        maximum = max(maximum, concurrent)
        entered.set()
        await release.wait()
        try:
            return await original(home)
        finally:
            concurrent -= 1

    with patch.object(api, "get_home_statuses", side_effect=delayed):
        first = asyncio.create_task(refresh(hass))
        await entered.wait()
        second = asyncio.create_task(refresh(hass))
        await asyncio.sleep(0)
        assert not first.done() and not second.done()
        simulator.state["rain"] = True
        release.set()
        await asyncio.gather(first, second)
    assert maximum == 1
    assert simulator.counts["homestatus"] == 2
    assert (
        entry.runtime_data.data[next(iter(entry.runtime_data.data))]["devices"][0].is_raining
        is True
    )


@pytest.mark.parametrize("failure", [503, 429, 403])
async def test_action_failure_backoff_and_automatic_recovery(hass, loaded, failure, caplog):
    entry, simulator, api = loaded
    simulator.state["outage"] = failure
    for _ in range(2):
        with pytest.raises(HomeAssistantError, match="refresh failed"):
            await refresh(hass)
    assert caplog.text.count("Error fetching velux_active data") == 1
    assert simulator.counts["password"] == 1
    if failure in (429, 403):
        assert simulator.counts["homestatus"] == 2
        simulator.state["outage"] = 0
        with pytest.raises(HomeAssistantError):
            await refresh(hass)
        assert simulator.counts["homestatus"] == 2
        # Advance the cloud deadline without delaying the test or changing HA internals.
        with patch("custom_components.velux_active.api.monotonic", return_value=api._retry_at + 1):
            async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=2))
            await hass.async_block_till_done(wait_background_tasks=True)
    else:
        simulator.state["outage"] = 0
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=2))
        await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.runtime_data.last_update_success
    assert caplog.text.count("Fetching velux_active data recovered") == 1


async def test_action_authentication_failure_starts_reauth(hass, loaded):
    entry, simulator, _ = loaded
    simulator.access.clear()
    simulator.refresh.clear()
    simulator.state["password"] = "renewed-password"
    with pytest.raises(HomeAssistantError):
        await refresh(hass)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress_by_handler("velux_active")
    assert len(flows) == 1 and flows[0]["context"]["entry_id"] == entry.entry_id


async def test_failed_unload_preserves_resources_and_successful_unload_cancels_owned_work(
    hass, loaded
):
    entry, _, api = loaded
    with patch.object(hass.config_entries, "async_unload_platforms", return_value=False):
        assert not await async_unload_entry(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    await refresh(hass)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def delayed(home):
        entered.set()
        await release.wait()
        return []

    coordinator = entry.runtime_data
    with patch.object(api, "get_home_statuses", side_effect=delayed):
        task = asyncio.create_task(refresh(hass))
        await entered.wait()
        queued = asyncio.create_task(refresh(hass))
        await asyncio.sleep(0)
        assert await hass.config_entries.async_unload(entry.entry_id)
        for caller in (task, queued):
            with pytest.raises(HomeAssistantError, match="unloaded"):
                await caller
    assert coordinator._manual_task.done()


@pytest.mark.parametrize("source", ["reauth", "reconfigure"])
async def test_account_renewal_rejects_switch_and_preserves_credentials_on_failures(
    hass, cloud, source
):
    _, api = cloud
    entry = MockConfigEntry(
        domain="velux_active", version=1, data={"username": USERNAME, "password": PASSWORD}
    )
    entry.add_to_hass(hass)
    with (
        patch("custom_components.velux_active.config_flow.VeluxActiveAPI", return_value=api),
        patch.object(hass.config_entries, "async_reload", return_value=True),
    ):
        flow = await hass.config_entries.flow.async_init(
            "velux_active",
            context={"source": source, "entry_id": entry.entry_id},
            data=entry.data if source == "reauth" else None,
        )
        fields = flow["data_schema"].schema
        assert next(key for key in fields if key == "username").default() == USERNAME
        assert fields[next(key for key in fields if key == "password")].config["type"] == "password"
        original_data = dict(entry.data)
        with patch.object(api, "authenticate", new_callable=AsyncMock) as authenticate:
            result = await hass.config_entries.flow.async_configure(
                flow["flow_id"], {"username": "other@example.invalid", "password": PASSWORD}
            )
            assert result["errors"] == {"base": "wrong_account"}
            authenticate.assert_not_called()
        for error, expected in [
            (InvalidAuthError(), "invalid_auth"),
            (APIConnectionError(), "cannot_connect"),
        ]:
            with patch.object(api, "authenticate", side_effect=error):
                result = await hass.config_entries.flow.async_configure(
                    flow["flow_id"], original_data
                )
                assert result["errors"] == {"base": expected}
                assert dict(entry.data) == original_data
        result = await hass.config_entries.flow.async_configure(flow["flow_id"], original_data)
        assert result["reason"] == source + "_successful"
        assert entry.entry_id in {
            e.entry_id for e in hass.config_entries.async_entries("velux_active")
        }


async def test_single_entry_rejects_duplicate_user_flow(hass):
    entry = MockConfigEntry(
        domain="velux_active", data={"username": USERNAME, "password": PASSWORD}
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init("velux_active", context={"source": "user"})
    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.parametrize(
    "error,state",
    [
        (APIConnectionError(), ConfigEntryState.SETUP_RETRY),
        (InvalidAuthError(), ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_first_refresh_validates_setup_before_entities(hass, error, state):
    entry = MockConfigEntry(
        domain="velux_active", data={"username": USERNAME, "password": PASSWORD}
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.velux_active.coordinator.VeluxActiveAPI.authenticate", side_effect=error
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is state
    assert not er.async_get(hass).entities
    assert hass.services.has_service("velux_active", "refresh")
    with pytest.raises(ServiceValidationError):
        await refresh(hass)


async def test_cancelling_one_waiter_leaves_shared_update_running(hass, loaded):
    entry, simulator, api = loaded
    entered = asyncio.Event()
    release = asyncio.Event()
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
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert not entry.runtime_data._manual_task.done()
        release.set()
        await second
    assert simulator.counts["homestatus"] == 2


async def test_native_failed_unload_reports_framework_state_and_rejects_action(hass, loaded):
    entry, _, _ = loaded
    coordinator = entry.runtime_data
    with patch.object(hass.config_entries, "async_unload_platforms", return_value=False):
        assert not await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.FAILED_UNLOAD
    assert entry.runtime_data is coordinator
    with pytest.raises(ServiceValidationError):
        await refresh(hass)
    # HA considers FAILED_UNLOAD unrecoverable; explicitly clean only test resources.
    await hass.config_entries.async_unload_platforms(entry, ["cover", "sensor", "binary_sensor"])
    await coordinator.async_shutdown()


async def test_synthetic_legacy_v1_registry_preserved_by_update_reload_and_reauth(hass, cloud):
    import json
    from pathlib import Path

    from homeassistant.helpers import device_registry as dr

    fixture = json.loads(await asyncio.to_thread(Path("tests/fixtures/legacy_v1.json").read_text))
    simulator, api = cloud
    entry = MockConfigEntry(
        domain="velux_active",
        entry_id=fixture["entry_id"],
        version=fixture["version"],
        data={"username": USERNAME, "password": PASSWORD},
    )
    entry.add_to_hass(hass)
    entities = er.async_get(hass)
    devices = dr.async_get(hass)
    device_ids = {}
    for item in fixture["entities"]:
        if item["device"] not in device_ids:
            device = devices.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers={("velux_active", item["device"])},
                name="Legacy device",
            )
            devices.async_update_device(device.id, name_by_user="My " + item["device"])
            device_ids[item["device"]] = device.id
        registered = entities.async_get_or_create(
            item["domain"],
            "velux_active",
            item["unique_id"],
            suggested_object_id=item["entity_id"].split(".", 1)[1],
            config_entry=entry,
            device_id=device_ids[item["device"]],
        )
        entities.async_update_entity(
            registered.entity_id,
            name=item["name"],
            disabled_by=er.RegistryEntryDisabler.USER if item["disabled"] else None,
        )

    def assert_identity():
        assert entry.entry_id == fixture["entry_id"] and entry.version == 1
        for item in fixture["entities"]:
            registered = entities.async_get(item["entity_id"])
            assert registered.unique_id == item["unique_id"]
            assert registered.config_entry_id == fixture["entry_id"]
            assert registered.name == item["name"]
            assert registered.disabled == item["disabled"]
            assert registered.device_id == device_ids[item["device"]]
            assert devices.async_get(registered.device_id).name_by_user == "My " + item["device"]
            if item["disabled"]:
                assert hass.states.get(item["entity_id"]) is None

    with patch("custom_components.velux_active.coordinator.VeluxActiveAPI", return_value=api):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert_identity()
        await refresh(hass)
        assert_identity()
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert_identity()
        simulator.state["password"] = "new-password"
        flow = await hass.config_entries.flow.async_init(
            "velux_active",
            context={"source": "reauth", "entry_id": entry.entry_id},
            data=entry.data,
        )
        with patch("custom_components.velux_active.config_flow.VeluxActiveAPI", return_value=api):
            result = await hass.config_entries.flow.async_configure(
                flow["flow_id"], {"username": USERNAME, "password": "new-password"}
            )
        assert result["reason"] == "reauth_successful"
        await hass.async_block_till_done()
        assert_identity()
