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
        with patch("velux_active_client.client.monotonic", return_value=api._retry_at + 1):
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
        expected_inventory = {item["unique_id"]: item["entity_id"] for item in fixture["entities"]}
        actual = [
            registered
            for registered in entities.entities.values()
            if registered.config_entry_id == entry.entry_id
        ]
        assert len(actual) == len(expected_inventory)
        assert {
            registered.unique_id: registered.entity_id for registered in actual
        } == expected_inventory
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
            else:
                assert hass.states.get(item["entity_id"]) is not None
        assert hass.states.get("binary_sensor.gateway_lab_gateway_is_raining").state == (
            "on" if simulator.state["rain"] else "off"
        )

    with patch("custom_components.velux_active.coordinator.VeluxActiveAPI", return_value=api):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert_identity()
        simulator.state["rain"] = True
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


@pytest.mark.parametrize("value", [[], {}, "", "false", "true", 0, 1])
async def test_invalid_wire_rain_fails_native_refresh_and_recovers(hass, loaded, value):
    entry, simulator, _ = loaded
    registry = er.async_get(hass)
    rain = registry.async_get_entity_id("binary_sensor", "velux_active", "lab-gateway_is_raining")
    assert hass.states.get(rain).state == "off"
    simulator.state["rain"] = value
    with pytest.raises(HomeAssistantError, match="refresh failed"):
        await refresh(hass)
    assert hass.states.get(rain).state == "unavailable"
    simulator.state["rain"] = None
    await refresh(hass)
    assert hass.states.get(rain).state == "unknown"
    simulator.state["rain"] = False
    await refresh(hass)
    assert hass.states.get(rain).state == "off"
    simulator.state["rain"] = True
    await refresh(hass)
    assert hass.states.get(rain).state == "on"
    assert entry.runtime_data.last_update_success


async def test_device_disconnection_and_recovery_logs_are_deduplicated(hass, loaded, caplog):
    _, simulator, _ = loaded
    for reachable in (False, False, True, True):
        simulator.state["reachable"] = reachable
        await refresh(hass)
    messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "custom_components.velux_active.coordinator"
        and record.levelname == "INFO"
    ]
    assert messages == ["VELUX device 1 is unavailable", "VELUX device 1 recovered"]
    assert "lab-gateway" not in " ".join(messages)


async def test_legacy_identity_oracle_rejects_deliberate_rain_unique_id_mutation(hass, cloud):
    from custom_components.velux_active.binary_sensor import VeluxBinarySensor

    initialize = VeluxBinarySensor.__init__

    def mutate(entity, *args, **kwargs):
        initialize(entity, *args, **kwargs)
        if entity._attribute == "is_raining":
            entity._attr_unique_id += "_mutation"

    with patch.object(VeluxBinarySensor, "__init__", mutate), pytest.raises(AssertionError):
        await test_synthetic_legacy_v1_registry_preserved_by_update_reload_and_reauth(hass, cloud)


async def test_topology_cadence_retains_inventory_on_failure_and_status_continues(hass, loaded):
    entry, simulator, _ = loaded
    coordinator = entry.runtime_data
    topology_observed = coordinator.topology_observed_at
    old_homes = coordinator.homes
    attempt = coordinator.topology_attempted_at
    simulator.state["topology_outage"] = 503
    with patch("custom_components.velux_active.coordinator.monotonic", return_value=attempt + 299):
        await refresh(hass)
    assert simulator.counts["homesdata"] == 1
    with patch("custom_components.velux_active.coordinator.monotonic", return_value=attempt + 300):
        await refresh(hass)
    assert simulator.counts["homesdata"] == 2
    assert coordinator.topology_failed
    assert coordinator.topology_observed_at == topology_observed
    assert coordinator.status_observed_at == attempt + 300
    assert coordinator.homes == old_homes
    with patch("custom_components.velux_active.coordinator.monotonic", return_value=attempt + 599):
        await refresh(hass)
    assert simulator.counts["homesdata"] == 2
    simulator.state["topology_outage"] = 0
    with patch("custom_components.velux_active.coordinator.monotonic", return_value=attempt + 600):
        await refresh(hass)
    assert simulator.counts["homesdata"] == 3
    assert not coordinator.topology_failed
    assert coordinator.topology_observed_at == attempt + 600


@pytest.mark.parametrize("status", [401, 429])
async def test_terminal_topology_failure_cannot_be_hidden_by_status_success(hass, loaded, status):
    entry, simulator, _ = loaded
    simulator.state["topology_outage"] = status
    old_status_calls = simulator.counts["homestatus"]
    due = entry.runtime_data.topology_attempted_at + 300
    with patch("custom_components.velux_active.coordinator.monotonic", return_value=due):
        with pytest.raises(HomeAssistantError):
            await refresh(hass)
    assert simulator.counts["homestatus"] == old_status_calls
    assert entry.runtime_data.topology_failed


async def test_omitted_known_device_logs_one_outage_and_recovery(hass, loaded, caplog):
    _, simulator, _ = loaded
    registry = er.async_get(hass)
    rain = registry.async_get_entity_id("binary_sensor", "velux_active", "lab-gateway_is_raining")
    simulator.state["status_payload"] = {"body": {"home": {"modules": []}}}
    caplog.set_level("INFO", logger="custom_components.velux_active.coordinator")
    await refresh(hass)
    await refresh(hass)
    assert hass.states.get(rain).state == "unavailable"
    assert sum("is unavailable" in r.message for r in caplog.records) == 4
    del simulator.state["status_payload"]
    await refresh(hass)
    await refresh(hass)
    assert hass.states.get(rain).state == "off"
    assert sum("recovered" in r.message for r in caplog.records) == 4


async def test_existing_device_home_move_keeps_original_live_entity(hass, loaded):
    from tests.lab.cloud import TOPOLOGY

    entry, simulator, _ = loaded
    registry = er.async_get(hass)
    rain = registry.async_get_entity_id("binary_sensor", "velux_active", "lab-gateway_is_raining")
    before = set(registry.entities)
    simulator.state["topology_payload"] = {
        "body": {"homes": [{"id": "new-synthetic-home", "name": "Renamed", "modules": TOPOLOGY}]}
    }
    simulator.state["status_payload"] = {
        "body": {
            "home": {"modules": [{"id": "lab-gateway", "is_raining": True, "reachable": True}]}
        }
    }
    due = entry.runtime_data.topology_attempted_at + 300
    with patch("custom_components.velux_active.coordinator.monotonic", return_value=due):
        await refresh(hass)
    assert hass.states.get(rain).state == "on"
    assert set(registry.entities) == before


async def test_dynamic_device_addition_updates_registry_without_reload(hass, loaded):
    from homeassistant.helpers import device_registry as dr

    from tests.lab.cloud import HOME, TOPOLOGY

    entry, simulator, _ = loaded
    registry = er.async_get(hass)
    original = set(registry.entities)
    simulator.state["topology_payload"] = {
        "body": {
            "homes": [
                {
                    "id": HOME,
                    "name": "Renamed",
                    "modules": TOPOLOGY
                    + [{"id": "new-gateway", "type": "NXG", "name": "Synthetic new gateway"}],
                }
            ]
        }
    }
    simulator.state["status_payload"] = {
        "body": {
            "home": {"modules": [{"id": "new-gateway", "is_raining": True, "reachable": True}]}
        }
    }
    due = entry.runtime_data.topology_attempted_at + 300
    with patch("custom_components.velux_active.coordinator.monotonic", return_value=due):
        await refresh(hass)
        await hass.async_block_till_done()
        await refresh(hass)
        await hass.async_block_till_done()
    rain = registry.async_get_entity_id("binary_sensor", "velux_active", "new-gateway_is_raining")
    assert hass.states.get(rain).state == "on"
    assert original <= set(registry.entities)
    entities = [e for e in registry.entities.values() if e.unique_id == "new-gateway_is_raining"]
    assert len(entities) == 1
    device = dr.async_get(hass).async_get_device_by_identifier(
        ("velux_active", "new-gateway"), entry.entry_id
    )
    assert device.name == "Synthetic new gateway"
    assert entry.state is ConfigEntryState.LOADED


async def test_empty_account_keeps_entry_discovery_listener(hass, cloud):
    from tests.lab.cloud import HOME, TOPOLOGY

    simulator, api = cloud
    simulator.state["topology_payload"] = {"body": {"homes": []}}
    entry = MockConfigEntry(
        domain="velux_active", version=1, data={"username": USERNAME, "password": PASSWORD}
    )
    entry.add_to_hass(hass)
    with patch("custom_components.velux_active.coordinator.VeluxActiveAPI", return_value=api):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        simulator.state["topology_payload"] = {
            "body": {"homes": [{"id": HOME, "name": "Synthetic", "modules": TOPOLOGY}]}
        }
        due = entry.runtime_data.topology_attempted_at + 300
        with patch("custom_components.velux_active.coordinator.monotonic", return_value=due):
            async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=61))
            await hass.async_block_till_done(wait_background_tasks=True)
        rain = er.async_get(hass).async_get_entity_id(
            "binary_sensor", "velux_active", "lab-gateway_is_raining"
        )
        assert hass.states.get(rain).state == "off"


async def test_manual_removal_requires_fresh_complete_uncontradicted_inventory(hass, loaded):
    from homeassistant.helpers import device_registry as dr

    from custom_components.velux_active import async_remove_config_entry_device
    from tests.lab.cloud import HOME

    entry, simulator, _ = loaded
    coordinator = entry.runtime_data
    device = dr.async_get(hass).async_get_device_by_identifier(
        ("velux_active", "lab-gateway"), entry.entry_id
    )
    assert not await async_remove_config_entry_device(hass, entry, device)
    due = coordinator.topology_attempted_at + 300
    simulator.state["topology_payload"] = {"body": {"homes": [{"id": HOME, "modules": []}]}}
    # An unsupported ID in same-cycle status vetoes absence too.
    simulator.state["status_payload"] = {
        "body": {"home": {"modules": [{"id": "lab-gateway", "type": "FUTURE"}]}}
    }
    with patch("custom_components.velux_active.coordinator.monotonic", return_value=due):
        await refresh(hass)
        assert not await async_remove_config_entry_device(hass, entry, device)
        simulator.state["status_payload"] = {"body": {"home": {"modules": []}}}
        await refresh(hass)
        assert not await async_remove_config_entry_device(hass, entry, device)
    with patch("custom_components.velux_active.coordinator.monotonic", return_value=due + 300):
        await refresh(hass)
        assert await async_remove_config_entry_device(hass, entry, device)
        # Permission is not deletion.
        assert dr.async_get(hass).async_get(device.id) is device
    with patch("custom_components.velux_active.coordinator.monotonic", return_value=due + 600):
        assert not await async_remove_config_entry_device(hass, entry, device)
        simulator.state["topology_outage"] = 503
        await refresh(hass)
        assert not await async_remove_config_entry_device(hass, entry, device)
    with patch("custom_components.velux_active.coordinator.monotonic", return_value=due + 900):
        simulator.state["topology_outage"] = 0
        await refresh(hass)
        assert await async_remove_config_entry_device(hass, entry, device)


async def test_native_removal_preserves_other_owner_and_reappearance(hass, loaded, hass_ws_client):
    from homeassistant.helpers import device_registry as dr
    from homeassistant.setup import async_setup_component

    from tests.lab.cloud import HOME

    entry, simulator, _ = loaded
    registry = dr.async_get(hass)
    device = registry.async_get_device_by_identifier(
        ("velux_active", "lab-gateway"), entry.entry_id
    )
    other = MockConfigEntry(domain="test", data={})
    other.add_to_hass(hass)
    other_device = registry.async_get_or_create(
        config_entry_id=other.entry_id,
        identifiers={("velux_active", "lab-gateway")},
        name="Other owner's device",
    )
    assert other_device.id != device.id
    assert await async_setup_component(hass, "config", {})
    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": "config/device_registry/remove", "device_id": device.id}
    )
    denied = await client.receive_json()
    assert denied["success"] is False
    simulator.state["topology_payload"] = {"body": {"homes": [{"id": HOME, "modules": []}]}}
    simulator.state["status_payload"] = {"body": {"home": {"modules": []}}}
    due = entry.runtime_data.topology_attempted_at + 300
    with patch("custom_components.velux_active.coordinator.monotonic", return_value=due):
        await refresh(hass)
        await client.send_json(
            {"id": 2, "type": "config/device_registry/remove", "device_id": device.id}
        )
        accepted = await client.receive_json()
        assert accepted["success"] is True
        await hass.async_block_till_done()
        assert registry.async_get(device.id) is None
        assert registry.async_get(other_device.id) is not None
    del simulator.state["topology_payload"]
    del simulator.state["status_payload"]
    with patch("custom_components.velux_active.coordinator.monotonic", return_value=due + 300):
        await refresh(hass)
        await hass.async_block_till_done()
    rain = er.async_get(hass).async_get_entity_id(
        "binary_sensor", "velux_active", "lab-gateway_is_raining"
    )
    assert hass.states.get(rain).state == "off"
    assert (
        len(
            [
                e
                for e in er.async_get(hass).entities.values()
                if e.unique_id == "lab-gateway_is_raining"
            ]
        )
        == 1
    )
    assert registry.async_get(other_device.id) is not None


async def test_removal_is_denied_while_refresh_has_only_partial_observations(hass, loaded):
    from homeassistant.helpers import device_registry as dr

    from custom_components.velux_active import async_remove_config_entry_device
    from tests.lab.cloud import HOME

    entry, simulator, api = loaded
    device = dr.async_get(hass).async_get_device_by_identifier(
        ("velux_active", "lab-gateway"), entry.entry_id
    )
    simulator.state["topology_payload"] = {"body": {"homes": [{"id": HOME, "modules": []}]}}
    simulator.state["status_payload"] = {"body": {"home": {"modules": []}}}
    entered, release = asyncio.Event(), asyncio.Event()
    original = api.get_home_statuses

    async def delayed(home):
        entered.set()
        await release.wait()
        return await original(home)

    due = entry.runtime_data.topology_attempted_at + 300
    with (
        patch("custom_components.velux_active.coordinator.monotonic", return_value=due),
        patch.object(api, "get_home_statuses", side_effect=delayed),
    ):
        operation = asyncio.create_task(refresh(hass))
        await entered.wait()
        assert not await async_remove_config_entry_device(hass, entry, device)
        release.set()
        await operation
        assert await async_remove_config_entry_device(hass, entry, device)


async def test_all_disabled_entities_keep_native_polling_and_discovery(hass, loaded):
    from tests.lab.cloud import HOME, TOPOLOGY

    entry, simulator, _ = loaded
    registry = er.async_get(hass)
    for entity in tuple(registry.entities.values()):
        if entity.config_entry_id == entry.entry_id:
            registry.async_update_entity(
                entity.entity_id, disabled_by=er.RegistryEntryDisabler.USER
            )
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    simulator.state["topology_payload"] = {
        "body": {
            "homes": [
                {"id": HOME, "modules": TOPOLOGY + [{"id": "new-disabled-test", "type": "NXG"}]}
            ]
        }
    }
    simulator.state["status_payload"] = {
        "body": {
            "home": {
                "modules": [{"id": "new-disabled-test", "is_raining": False, "reachable": True}]
            }
        }
    }
    due = entry.runtime_data.topology_attempted_at + 300
    with patch("custom_components.velux_active.coordinator.monotonic", return_value=due):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=61))
        await hass.async_block_till_done(wait_background_tasks=True)
    rain = registry.async_get_entity_id(
        "binary_sensor", "velux_active", "new-disabled-test_is_raining"
    )
    assert hass.states.get(rain).state == "off"
    original = registry.async_get_entity_id(
        "binary_sensor", "velux_active", "lab-gateway_is_raining"
    )
    assert registry.async_get(original).disabled_by is er.RegistryEntryDisabler.USER


async def test_sparse_status_presence_survives_model_failure_and_later_omission(hass, loaded):
    from homeassistant.helpers import device_registry as dr

    from custom_components.velux_active import async_remove_config_entry_device
    from tests.lab.cloud import HOME

    entry, simulator, _ = loaded
    device = dr.async_get(hass).async_get_device_by_identifier(
        ("velux_active", "lab-gateway"), entry.entry_id
    )
    simulator.state["topology_payload"] = {"body": {"homes": [{"id": HOME, "modules": []}]}}
    due = entry.runtime_data.topology_attempted_at + 300
    with patch("custom_components.velux_active.coordinator.monotonic", return_value=due):
        # Original sparse status positively reports IDs with no type metadata now.
        with pytest.raises(HomeAssistantError):
            await refresh(hass)
        assert not await async_remove_config_entry_device(hass, entry, device)
        simulator.state["status_payload"] = {"body": {"home": {"modules": []}}}
        await refresh(hass)
        assert not await async_remove_config_entry_device(hass, entry, device)
    with patch("custom_components.velux_active.coordinator.monotonic", return_value=due + 300):
        await refresh(hass)
        assert await async_remove_config_entry_device(hass, entry, device)


async def test_unknown_reachability_uses_effective_availability_transition(hass, loaded, caplog):
    _, simulator, _ = loaded
    caplog.set_level("INFO", logger="custom_components.velux_active.coordinator")
    rain = er.async_get(hass).async_get_entity_id(
        "binary_sensor", "velux_active", "lab-gateway_is_raining"
    )
    for reachable, expected in [(False, "unavailable"), (None, "off"), (None, "off")]:
        simulator.state["reachable"] = reachable
        await refresh(hass)
        assert hass.states.get(rain).state == expected
    assert sum("is unavailable" in r.message for r in caplog.records) == 1
    assert sum("recovered" in r.message for r in caplog.records) == 1


async def test_initial_unknown_reachability_then_omission_is_logged(hass, cloud, caplog):
    simulator, api = cloud
    simulator.state["reachable"] = None
    entry = MockConfigEntry(
        domain="velux_active", version=1, data={"username": USERNAME, "password": PASSWORD}
    )
    entry.add_to_hass(hass)
    with patch("custom_components.velux_active.coordinator.VeluxActiveAPI", return_value=api):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        caplog.set_level("INFO", logger="custom_components.velux_active.coordinator")
        simulator.state["status_payload"] = {"body": {"home": {"modules": []}}}
        await refresh(hass)
        await refresh(hass)
        assert sum("is unavailable" in r.message for r in caplog.records) == 4
        del simulator.state["status_payload"]
        await refresh(hass)
        assert sum("recovered" in r.message for r in caplog.records) == 4


async def test_removal_denies_unknown_owner_ambiguous_identity_and_uninitialized_inventory(
    hass, loaded
):
    from homeassistant.helpers import device_registry as dr

    from custom_components.velux_active import async_remove_config_entry_device

    entry, _, _ = loaded
    registry = dr.async_get(hass)
    other = MockConfigEntry(domain="test", data={})
    other.add_to_hass(hass)
    wrong = registry.async_get_or_create(
        config_entry_id=other.entry_id, identifiers={("velux_active", "absent")}
    )
    assert not await async_remove_config_entry_device(hass, entry, wrong)
    ambiguous = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("velux_active", "absent-one"), ("velux_active", "absent-two")},
    )
    assert not await async_remove_config_entry_device(hass, entry, ambiguous)
    coordinator = entry.runtime_data
    coordinator.topology_observed_at = None
    assert not coordinator.async_can_remove_device("absent")
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert not await async_remove_config_entry_device(hass, entry, ambiguous)


@pytest.mark.parametrize("malformed_first", [True, False])
@pytest.mark.parametrize("nested_error", [True, False])
async def test_status_presence_veto_survives_malformed_siblings_and_nested_errors(
    hass, loaded, malformed_first, nested_error
):
    from homeassistant.helpers import device_registry as dr

    from custom_components.velux_active import async_remove_config_entry_device
    from tests.lab.cloud import HOME

    entry, simulator, _ = loaded
    device = dr.async_get(hass).async_get_device_by_identifier(
        ("velux_active", "lab-gateway"), entry.entry_id
    )
    simulator.state["topology_payload"] = {"body": {"homes": [{"id": HOME, "modules": []}]}}
    records = [None, {"id": "lab-gateway", "type": "FUTURE"}]
    if not malformed_first:
        records.reverse()
    body = {"home": {"modules": records}}
    if nested_error:
        body["errors"] = [{"code": 2}]
    simulator.state["status_payload"] = {"body": body}
    due = entry.runtime_data.topology_attempted_at + 300
    with patch("custom_components.velux_active.coordinator.monotonic", return_value=due):
        with pytest.raises(HomeAssistantError):
            await refresh(hass)
        assert not await async_remove_config_entry_device(hass, entry, device)
        simulator.state["status_payload"] = {"body": {"home": {"modules": []}}}
        await refresh(hass)
        assert not await async_remove_config_entry_device(hass, entry, device)
    with patch("custom_components.velux_active.coordinator.monotonic", return_value=due + 300):
        await refresh(hass)
        assert await async_remove_config_entry_device(hass, entry, device)


@pytest.fixture
async def migrated_composite_ready(hass, cloud, hass_storage):
    import copy
    import json
    from pathlib import Path

    simulator, api = cloud
    entry = MockConfigEntry(
        domain="velux_active", version=1, data={"username": USERNAME, "password": PASSWORD}
    )
    other = MockConfigEntry(domain="test", data={})
    entry.add_to_hass(hass)
    other.add_to_hass(hass)
    storage = json.loads((Path(__file__).parents[1] / "fixtures/legacy_storage.json").read_text())
    device = copy.deepcopy(storage["core.device_registry"]["data"]["devices"][0])
    old_id = device["id"]
    device["identifiers"] = [["velux_active", "lab-gateway"]]
    device["config_entries"] = [entry.entry_id, other.entry_id]
    device["config_entries_subentries"] = {entry.entry_id: [None], other.entry_id: [None]}
    device["primary_config_entry"] = entry.entry_id
    device["name_by_user"] = "Shared custom name"
    for key in (
        "config_entry_id",
        "config_subentry_id",
        "composite_device_id",
        "composite_primary_config_entry",
        "split_at",
        "has_composite_identifiers",
    ):
        device.pop(key, None)
    hass_storage["core.device_registry"] = {
        "version": 1,
        "minor_version": 12,
        "data": {"devices": [device], "deleted_devices": []},
    }
    from homeassistant.helpers import device_registry as dr

    dr.async_setup(hass)
    await dr.async_load(hass)
    await er.async_load(hass)
    with patch("custom_components.velux_active.coordinator.VeluxActiveAPI", return_value=api):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield hass, entry, other, simulator, old_id
        assert await hass.config_entries.async_unload(entry.entry_id)
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
        await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.parametrize("load_registries", [False])
async def test_native_migrated_composite_rejected_and_underlying_removal_preserves_other(
    migrated_composite_ready, hass_ws_client, load_registries
):
    from homeassistant.helpers import device_registry as dr
    from homeassistant.setup import async_setup_component

    from tests.lab.cloud import HOME

    hass, entry, other, simulator, old_id = migrated_composite_ready
    registry = dr.async_get(hass)
    own_device = registry.async_get_device_by_identifier(
        ("velux_active", "lab-gateway"), entry.entry_id
    )
    other_device = registry.async_get_device_by_identifier(
        ("velux_active", "lab-gateway"), other.entry_id
    )
    assert own_device.composite_device_id == other_device.composite_device_id == old_id
    entity = er.async_get(hass).async_get_or_create(
        "sensor",
        "test",
        "other-unique",
        config_entry=other,
        device_id=other_device.id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    er.async_get(hass).async_update_entity(entity.entity_id, name="Other custom entity")
    assert await async_setup_component(hass, "config", {})
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "config/device_registry/remove", "device_id": old_id})
    assert (await client.receive_json())["success"] is False
    simulator.state["topology_payload"] = {"body": {"homes": [{"id": HOME, "modules": []}]}}
    simulator.state["status_payload"] = {"body": {"home": {"modules": []}}}
    due = entry.runtime_data.topology_attempted_at + 300
    with patch("custom_components.velux_active.coordinator.monotonic", return_value=due):
        await refresh(hass)
        await client.send_json(
            {"id": 2, "type": "config/device_registry/remove", "device_id": own_device.id}
        )
        assert (await client.receive_json())["success"] is True
    await hass.async_block_till_done()
    assert registry.async_get(own_device.id) is None
    assert registry.async_get(other_device.id).name_by_user == "Shared custom name"
    remaining = er.async_get(hass).async_get(entity.entity_id)
    assert remaining.name == "Other custom entity"
    assert remaining.disabled_by is er.RegistryEntryDisabler.USER
    assert remaining.device_id == other_device.id
    # Registries loaded after HA startup schedule native delayed association cleanup.
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert registry.async_get(other_device.id) is not None


async def test_native_child_device_removal_preserves_parent(hass, loaded, hass_ws_client):
    from homeassistant.helpers import device_registry as dr
    from homeassistant.setup import async_setup_component

    entry, _, _ = loaded
    registry = dr.async_get(hass)
    parent = registry.async_get_device_by_identifier(
        ("velux_active", "lab-gateway"), entry.entry_id
    )
    child = registry.async_get_or_create_child(
        config_entry_id=entry.entry_id,
        parent_device_id=parent.id,
        identifiers={("velux_active", "absent-child")},
        name="Synthetic child",
    )
    assert await async_setup_component(hass, "config", {})
    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": "config/device_registry/remove", "device_id": child.id}
    )
    assert (await client.receive_json())["success"] is True
    assert registry.async_get(child.id) is None
    assert registry.async_get(parent.id) is not None


@pytest.mark.parametrize("reverse", [False, True])
async def test_contradictory_duplicate_rain_status_fails_atomically_and_recovers(
    hass, loaded, reverse
):
    entry, simulator, _ = loaded
    rain = er.async_get(hass).async_get_entity_id(
        "binary_sensor", "velux_active", "lab-gateway_is_raining"
    )
    records = [
        {"id": "lab-gateway", "is_raining": False, "reachable": True},
        {"id": "lab-gateway", "is_raining": True, "reachable": True},
    ]
    if reverse:
        records.reverse()
    simulator.state["status_payload"] = {"body": {"home": {"modules": records}}}
    with pytest.raises(HomeAssistantError):
        await refresh(hass)
    assert entry.runtime_data.last_update_success is False
    assert hass.states.get(rain).state == "unavailable"
    assert "lab-gateway" in entry.runtime_data.api.status_presence
    del simulator.state["status_payload"]
    await refresh(hass)
    assert hass.states.get(rain).state == "off"
