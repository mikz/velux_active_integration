"""Lab-only assertions over installed artifacts and native HA; never shipped."""

import asyncio
import hashlib
import importlib.util
import json
import os
import sys
import zipfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, patch

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import SupportsResponse
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

DOMAIN = "lab_probe"
CONFIG_SCHEMA = vol.Schema({vol.Optional(DOMAIN): {}}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    if not os.environ.get("LAB_RUN_ID") or not await hass.async_add_executor_job(
        Path("/config/.lab-artifact-sha256").is_file
    ):
        raise RuntimeError("Artifact probe requires the prepared synthetic lab")

    async def run(call):
        if call.data["case"] == "discovery":
            return await discovery(hass)
        entry = next(
            entry
            for entry in hass.config_entries.async_entries("velux_active")
            if entry.state is ConfigEntryState.LOADED
        )
        case = call.data["case"]
        if case in ("retry-auth", "retry-topology"):
            try:
                return await setup_retry(hass, entry, case == "retry-topology")
            finally:
                await configure(hass, {"outage": 0, "topology_outage": 0, "retry_after": "2"})
                if entry.state is ConfigEntryState.LOADED:
                    assert await hass.config_entries.async_unload(entry.entry_id)
                    await hass.async_block_till_done()
        if case == "proof":
            return await hass.async_add_executor_job(installed_proof)
        if case == "topology":
            try:
                return await topology(hass, entry)
            finally:
                await configure(hass, {"reset_payloads": True})
                if entry.state is ConfigEntryState.LOADED:
                    assert await hass.config_entries.async_reload(entry.entry_id)
                    await hass.async_block_till_done()
        if case == "budgets":
            try:
                return await budgets(hass, entry)
            finally:
                await configure(
                    hass,
                    {
                        "reset_payloads": True,
                        "outage": 0,
                        "reject_refresh": False,
                        "status_delay": 0,
                    },
                )
                if entry.state is ConfigEntryState.LOADED:
                    coordinator = entry.runtime_data
                    assert await hass.config_entries.async_unload(entry.entry_id)
                    await hass.async_block_till_done()
                    assert not coordinator._listeners and coordinator._unsub_refresh is None
        if case == "statistics":
            return await statistics(hass, entry)
        if case == "automatic":
            return await automatic(hass, entry)
        if case == "new-defaults":
            return await new_defaults(hass, entry)
        if case == "reappear":
            return await reappear(hass, entry)
        if case == "registry":
            devices = dr.async_get(hass)
            own = devices.async_get_device_by_identifier(
                ("velux_active", "absent-composite"), entry.entry_id
            )
            other = devices.async_get_device_by_identifier(
                ("velux_active", "absent-composite"), "synthetic-other-entry"
            )
            assert (
                own.composite_device_id
                == other.composite_device_id
                == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            )
            other_entity = er.async_get(hass).async_get("sensor.other_retained")
            assert (
                other_entity.device_id == other.id
                and other_entity.disabled_by is er.RegistryEntryDisabler.USER
            )
            parent = devices.async_get_device_by_identifier(
                ("velux_active", "lab-gateway"), entry.entry_id
            )
            child = devices.async_get_or_create_child(
                config_entry_id=entry.entry_id,
                parent_device_id=parent.id,
                identifiers={("velux_active", "absent-child")},
                name="Synthetic child",
            )
            return {
                "own": own.id,
                "other": other.id,
                "composite": own.composite_device_id,
                "child": child.id,
                "parent": parent.id,
            }
        if case == "cleanup":
            return await cleanup(hass, entry)
        raise ValueError("Unknown lab acceptance case")

    hass.services.async_register(
        DOMAIN,
        "run",
        run,
        schema=vol.Schema({vol.Required("case"): str}),
        supports_response=SupportsResponse.ONLY,
    )
    return True


async def configure(hass, changes):
    session = async_get_clientsession(hass)
    async with session.post("https://app.velux-active.com/admin/state", json=changes) as response:
        assert response.status == 200
        return await response.json()


async def action(hass):
    await hass.services.async_call("velux_active", "refresh", {}, blocking=True)
    await hass.async_block_till_done()


async def cleanup(hass, entry):
    """Cancellation of one caller leaves shared work; unload cancels owned work."""
    from homeassistant.exceptions import HomeAssistantError

    old = entry.runtime_data
    session = async_get_clientsession(hass)
    tasks = []
    await configure(hass, {"status_delay": 1})

    async def invoke():
        # The parent probe owns the block-until-done boundary; child waiters must
        # not wait for that parent while it is awaiting their service results.
        await hass.services.async_call("velux_active", "refresh", {}, blocking=True)

    async def entered(before):
        for _ in range(100):
            if len((await configure(hass, {}))["requests"]) > before:
                return
            await asyncio.sleep(0.01)
        raise AssertionError("Expected native refresh HTTP request")

    try:
        before = len((await configure(hass, {}))["requests"])
        first = asyncio.create_task(invoke())
        second = asyncio.create_task(invoke())
        tasks.extend((first, second))
        await entered(before)
        first.cancel()
        cancelled = await asyncio.gather(first, return_exceptions=True)
        assert isinstance(cancelled[0], asyncio.CancelledError)
        await second
        assert old.last_update_success
        assert len((await configure(hass, {}))["requests"]) == before + len(old.homes)
        before = len((await configure(hass, {}))["requests"])
        waiter = asyncio.create_task(invoke())
        tasks.append(waiter)
        await entered(before)
        assert await hass.config_entries.async_unload(entry.entry_id)
        outcome = await asyncio.gather(waiter, return_exceptions=True)
        assert isinstance(outcome[0], HomeAssistantError)
        await hass.async_block_till_done()
        assert not old._listeners and old._unsub_refresh is None
        assert old._manual_task is not None and old._manual_task.done()
        assert not session.closed
    finally:
        await configure(hass, {"status_delay": 0})
        # Assert candidate cleanup before cancelling any remaining probe caller.
        if entry.state is ConfigEntryState.LOADED:
            assert await hass.config_entries.async_unload(entry.entry_id)
        assert not old._listeners and old._unsub_refresh is None
        assert old._manual_task is None or old._manual_task.done()
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    hass.services.async_remove(DOMAIN, "run")
    return {
        "candidate_listeners": 0,
        "candidate_pending_manual": 0,
        "shared_session_open": True,
        "probe_service_removed": True,
        "cancelled_waiter_did_not_cancel_shared_work": True,
        "unload_returns_action_error_to_waiter": True,
    }


async def setup_retry(hass, entry, topology_failure):
    """Native setup/retry and corrective flows use real HTTP, fresh credentials."""
    from custom_components.velux_active.const import async_rate_limit_state

    clock = entry.runtime_data.topology_attempted_at
    original = dict(entry.data)
    old = entry.runtime_data
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not old._listeners and old._unsub_refresh is None
    changes = {"retry_after": "99999"}
    changes["topology_outage" if topology_failure else "outage"] = 429
    await configure(hass, changes)
    before = list((await configure(hass, {}))["requests"])
    with logical_time(clock):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.SETUP_RETRY
        deadline = async_rate_limit_state(hass).deadline
        first = list((await configure(hass, {}))["requests"])
        expected = [["/oauth2/token", "password"]]
        if topology_failure:
            expected.append(["/api/homesdata", None])
        assert first[len(before) :] == expected
    with logical_time(clock + 6):
        # HA's retry timer remains real and invokes the ordinary setup path.
        await asyncio.sleep(6)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.SETUP_RETRY
        assert (await configure(hass, {}))["requests"] == first
        assert async_rate_limit_state(hass).deadline == deadline
        flow = await hass.config_entries.flow.async_init(
            "velux_active", context={"source": "reconfigure", "entry_id": entry.entry_id}
        )
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], {"username": original["username"], "password": "replacement"}
        )
        assert result["errors"] == {"base": "cannot_connect"} and entry.data == original
        hass.config_entries.flow.async_abort(result["flow_id"])
        assert (await configure(hass, {}))["requests"] == first
    await configure(hass, {"outage": 0, "topology_outage": 0, "password": "replacement"})
    with logical_time(deadline):
        flow = await hass.config_entries.flow.async_init(
            "velux_active", context={"source": "reconfigure", "entry_id": entry.entry_id}
        )
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], {"username": original["username"], "password": "replacement"}
        )
        assert result["type"] == "abort" and result["reason"] == "reconfigure_successful"
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        assert entry.data["password"] == "replacement"
        assert entry.runtime_data is not old and entry.runtime_data.last_update_success
        await configure(hass, {"password": original["password"]})
        flow = await hass.config_entries.flow.async_init(
            "velux_active", context={"source": "reconfigure", "entry_id": entry.entry_id}
        )
        result = await hass.config_entries.flow.async_configure(flow["flow_id"], original)
        assert result["reason"] == "reconfigure_successful"
        await hass.async_block_till_done()
        assert entry.data == original
    return {
        "initial_endpoint": "topology" if topology_failure else "authentication",
        "initial_request_trace": expected,
        "native_retry_after_six_seconds_no_http": True,
        "blocked_corrective_flow_preserves_credentials": True,
        "expiry_accepts_fresh_credentials": True,
        "requires_process_restart": True,
    }


async def topology(hass, entry):
    """Clock-only fixtures leave all candidate decisions and HTTP paths intact."""
    from custom_components.velux_active import async_remove_config_entry_device
    from custom_components.velux_active.api import VeluxHome

    registry = er.async_get(hass)
    devices = dr.async_get(hass)
    coordinator = entry.runtime_data
    clock = coordinator.topology_attempted_at
    original_ids = {
        record.unique_id: record.entity_id
        for record in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    normal_modules = [
        {"id": "lab-gateway", "type": "NXG", "name": "Lab Gateway"},
        {"id": "lab-window", "type": "NXO", "velux_type": "window", "bridge": "lab-gateway"},
        {"id": "lab-shutter", "type": "NXO", "velux_type": "shutter", "bridge": "lab-gateway"},
        {"id": "lab-switch", "type": "NXS", "bridge": "lab-gateway"},
    ]
    moved = next(module for module in normal_modules if module["id"] == "lab-window")
    known = {
        "id": "lab-home",
        "name": "Renamed synthetic home",
        "modules": [module for module in normal_modules if module is not moved],
    }
    added = {
        "id": "new-home",
        "modules": [
            {"id": "new-gateway", "type": "NXG"},
            {"id": "unsupported-device", "type": "FUTURE"},
            moved,
        ],
    }
    status = {
        home["id"]: {
            "body": {
                "home": {
                    "modules": [
                        module | {"reachable": True, "is_raining": False, "current_position": 17}
                        for module in home["modules"]
                    ]
                }
            }
        }
        for home in (known, added)
    }
    await configure(
        hass, {"topology_payload": {"body": {"homes": [known, added]}}, "status_by_home": status}
    )
    with logical_time(clock + 300):
        await action(hass)
        assert all(
            registry.async_get_entity_id(record.split(".")[0], "velux_active", uid) == record
            for uid, record in original_ids.items()
        )
        new_id = registry.async_get_entity_id(
            "binary_sensor", "velux_active", "new-gateway_is_raining"
        )
        assert new_id and hass.states.get(new_id).state == "off"
        assert hass.states.get(original_ids["lab-window"]).attributes["current_position"] == 17
        new_device = devices.async_get_device_by_identifier(
            ("velux_active", "new-gateway"), entry.entry_id
        )
        assert not await async_remove_config_entry_device(hass, entry, new_device)
        assert "unsupported-device" in coordinator.api.inventory_ids
    # Status succeeds while a failed topology attempt retains inventory/time and denies removal.
    accepted = coordinator.topology_observed_at
    await configure(hass, {"topology_outage": 503})
    with logical_time(clock + 600):
        await action(hass)
        assert coordinator.last_update_success and coordinator.topology_failed
        assert coordinator.topology_observed_at == accepted
        assert not await async_remove_config_entry_device(hass, entry, new_device)
    # Omission cannot defeat positive same-cycle status; a later complete inventory resolves it.
    await configure(
        hass,
        {
            "topology_outage": 0,
            "topology_payload": {"body": {"homes": [known, {"id": "new-home", "modules": []}]}},
        },
    )
    with logical_time(clock + 900):
        await action(hass)
        assert not await async_remove_config_entry_device(hass, entry, new_device)
    await configure(
        hass,
        {
            "status_by_home": {
                "lab-home": status["lab-home"],
                "new-home": {"body": {"home": {"modules": []}}},
            }
        },
    )
    with logical_time(clock + 960):
        await action(hass)
        assert not await async_remove_config_entry_device(hass, entry, new_device)
    with logical_time(clock + 1200):
        await action(hass)
        assert await async_remove_config_entry_device(hass, entry, new_device)
        # The external runner exercises native WS deletion, rather than the hook doing deletion.
    # Preserve positive IDs before normalization, regardless of malformed sibling order.
    from homeassistant.exceptions import HomeAssistantError

    positive = {"id": "new-gateway"}
    variants = [
        {"modules": [None, positive]},
        {"modules": [positive, None]},
        {"modules": [None, positive], "errors": [{"code": 2}]},
    ]
    for index, variant in enumerate(variants):
        at = clock + 1500 + index * 600
        await configure(
            hass,
            {
                "status_by_home": {
                    "lab-home": status["lab-home"],
                    "new-home": {"body": {"home": variant}},
                }
            },
        )
        with logical_time(at):
            try:
                await action(hass)
            except HomeAssistantError:
                pass
            else:
                raise AssertionError("Malformed positive sparse status must fail")
            assert "new-gateway" in coordinator.api.status_presence
            assert not await async_remove_config_entry_device(hass, entry, new_device)
        await configure(
            hass,
            {
                "status_by_home": {
                    "lab-home": status["lab-home"],
                    "new-home": {"body": {"home": {"modules": []}}},
                }
            },
        )
        with logical_time(at + 60):
            await action(hass)
            assert not await async_remove_config_entry_device(hass, entry, new_device)
        with logical_time(at + 300):
            await action(hass)
            assert await async_remove_config_entry_device(hass, entry, new_device)
    await configure(hass, {"reset_payloads": True})
    # Reload uses the native lifecycle, discarding logical future timestamps.
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data is not coordinator
    assert not coordinator._listeners and coordinator._unsub_refresh is None
    assert coordinator._manual_task is None or coordinator._manual_task.done()
    assert entry.runtime_data.topology_observed_at < clock + 300
    assert isinstance(next(iter(entry.runtime_data.data)), VeluxHome)
    return {
        "dynamic_entity_id": new_id,
        "dynamic_device_id": new_device.id,
        "checks": [
            "dynamic_addition",
            "stable_ids_on_home_rename",
            "stable_live_window_on_home_move",
            "unsupported_inventory",
            "topology_failure_retention",
            "same_cycle_presence_veto",
            "veto_survives_status_omission",
            "qualified_absence",
            "native_reload_clock_reset",
            "sparse_malformed_first_presence_veto",
            "sparse_malformed_last_presence_veto",
            "nested_error_positive_presence_veto",
        ],
    }


async def new_defaults(hass, entry):
    """Use never-before-seen IDs; native deleted-record restoration retains choices."""
    clock = entry.runtime_data.topology_attempted_at
    modules = [
        {"id": "lab-gateway", "type": "NXG", "name": "Lab Gateway"},
        {"id": "lab-window", "type": "NXO", "velux_type": "window", "bridge": "lab-gateway"},
        {"id": "lab-shutter", "type": "NXO", "velux_type": "shutter", "bridge": "lab-gateway"},
        {"id": "lab-switch", "type": "NXS", "bridge": "lab-gateway"},
        {"id": "never-seen-localized", "type": "NXG", "name": "New Gateway"},
    ]
    await configure(
        hass,
        {
            "topology_payload": {"body": {"homes": [{"id": "lab-home", "modules": modules}]}},
            "status_payload": {
                "body": {
                    "home": {
                        "modules": [
                            module | {"is_raining": False, "reachable": True} for module in modules
                        ]
                    }
                }
            },
        },
    )
    with logical_time(clock + 300):
        await action(hass)
    # Retain synthetic HTTP data through native locale reloads, restoring real timestamps.
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    records = [
        record
        for record in er.async_entries_for_config_entry(registry, entry.entry_id)
        if record.unique_id.startswith("never-seen-localized_")
    ]
    assert records
    for record in records:
        noisy = record.unique_id.endswith(
            ("_wifi_strength", "_last_seen", "_unlocked", "_locking", "_calibrating", "_busy")
        )
        assert record.disabled_by == (er.RegistryEntryDisabler.INTEGRATION if noisy else None)
    rain = registry.async_get_entity_id(
        "binary_sensor", "velux_active", "never-seen-localized_is_raining"
    )
    device = dr.async_get(hass).async_get_device_by_identifier(
        ("velux_active", "never-seen-localized"), entry.entry_id
    )
    return {"rain_entity_id": rain, "device_id": device.id, "new_only_defaults_verified": True}


async def reappear(hass, entry):
    """Native refresh recreates a manually removed registry device without duplicates."""
    coordinator = entry.runtime_data
    registry = er.async_get(hass)
    assert (
        registry.async_get_entity_id("binary_sensor", "velux_active", "new-gateway_is_raining")
        is None
    )
    await configure(
        hass,
        {
            "topology_payload": {
                "body": {
                    "homes": [
                        {"id": "returning-home", "modules": [{"id": "new-gateway", "type": "NXG"}]}
                    ]
                }
            },
            "status_payload": {
                "body": {"home": {"modules": [{"id": "new-gateway", "is_raining": False}]}}
            },
        },
    )
    try:
        with logical_time(coordinator.topology_attempted_at + 300):
            await action(hass)
            entity_id = registry.async_get_entity_id(
                "binary_sensor", "velux_active", "new-gateway_is_raining"
            )
            assert entity_id and hass.states.get(entity_id).state == "off"
            matches = [
                record
                for record in registry.entities.values()
                if record.config_entry_id == entry.entry_id
                and record.unique_id == "new-gateway_is_raining"
            ]
            assert len(matches) == 1
            device = dr.async_get(hass).async_get_device_by_identifier(
                ("velux_active", "new-gateway"), entry.entry_id
            )
            return {
                "entity_id": entity_id,
                "device_id": device.id,
                "one_live_entity": True,
                "no_permanent_suppression": True,
            }
    finally:
        await configure(hass, {"reset_payloads": True})
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert not coordinator._listeners and coordinator._unsub_refresh is None


def installed_proof():
    """Inspect after native loading; never modify imports or the requirement path."""
    root = Path("/config/custom_components/velux_active")
    archive = Path("/opt/velux-active/velux_active.zip")
    with zipfile.ZipFile(archive) as payload:
        members = {
            name: hashlib.sha256(payload.read(name)).hexdigest() for name in payload.namelist()
        }
    for member, digest in members.items():
        assert hashlib.sha256((root / member).read_bytes()).hexdigest() == digest
    origins = {}
    for name, module in tuple(sys.modules.items()):
        if name == "custom_components.velux_active" or name.startswith(
            "custom_components.velux_active."
        ):
            origin = Path(module.__file__).resolve()
            assert origin.is_relative_to(root)
            origins[name] = origin.relative_to(root).as_posix()
    assert "custom_components.velux_active.coordinator" in origins
    spec = importlib.util.spec_from_file_location("artifact_proof_helper", "/lab/cloud_smoke.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    manifest = json.loads((root / "manifest.json").read_text())
    (wheel,) = Path("/opt/velux-active").glob("*.whl")
    client = helper.verify_dependency(wheel, manifest["requirements"])
    assert client["wheel_sha256"] == os.environ["LAB_CLIENT_WHEEL_SHA256"]
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == os.environ["LAB_ARTIFACT_SHA256"]
    return {
        "member_hashes": members,
        "native_origins": origins,
        "client": client,
        "clock_patch_targets": [
            "custom_components.velux_active.coordinator.monotonic",
            "velux_active_client.client.monotonic",
        ],
        "clock_scope": "logical decision/boundary proof; HA scheduler remains real",
    }


async def async_setup_entry(hass, entry):
    """The second synthetic integration owns its native underlying registry record."""
    return True


async def async_unload_entry(hass, entry):
    return True


@contextmanager
def logical_time(value):
    """Patch only the named candidate/client clocks; restore even on failure."""
    with (
        patch("custom_components.velux_active.coordinator.monotonic", return_value=value),
        patch("velux_active_client.client.monotonic", return_value=value),
    ):
        yield


async def discovery(hass):
    """Raw synthetic TXT traverses native routing and the actual account flow."""
    from dataclasses import replace
    from ipaddress import IPv4Address

    from homeassistant import loader
    from homeassistant.components.zeroconf.discovery import ZeroconfDiscovery, info_from_service
    from homeassistant.helpers import discovery_flow
    from zeroconf.asyncio import AsyncServiceInfo

    models = await loader.async_get_homekit(hass)
    types = await loader.async_get_zeroconf(hass)
    routes = []
    for model in (b"VELUX Gateway", b"VELUX Gateway\x00"):
        for paired in (False, True):
            service = AsyncServiceInfo(
                "_hap._tcp.local.",
                "Synthetic._hap._tcp.local.",
                server="synthetic.local.",
                port=12345,
                addresses=[IPv4Address("192.0.2.10").packed],
                properties={b"md": model, b"sf": b"0" if paired else b"1"},
            )
            router = ZeroconfDiscovery(hass, Mock(), types, models, {}, service)
            with patch.object(discovery_flow, "async_create_flow") as dispatch:
                router._async_process_service_update(service, service.type, service.name)
            domains = {call.args[1] for call in dispatch.call_args_list}
            assert "velux_active" in domains and "homekit_controller" in domains
            flow = await hass.config_entries.flow.async_init(
                "velux_active", context={"source": "homekit"}, data=info_from_service(service)
            )
            assert flow["step_id"] == "discovery_confirm"
            hass.config_entries.flow.async_abort(flow["flow_id"])
            routes.append(
                {
                    "terminal_nul": model.endswith(b"\x00"),
                    "paired": paired,
                    "cloud_hint": True,
                    "homekit_route": True,
                }
            )
    info = info_from_service(service)
    bad = replace(info, properties={**info.properties, "md": "VELUX Gateway-evil"})
    result = await hass.config_entries.flow.async_init(
        "velux_active", context={"source": "homekit"}, data=bad
    )
    assert result["reason"] == "not_supported"
    # Open one real native confirmation for the external REST caller to complete.
    flow = await hass.config_entries.flow.async_init(
        "velux_active", context={"source": "homekit"}, data=info_from_service(service)
    )
    assert flow["step_id"] == "discovery_confirm"
    return {"flow_id": flow["flow_id"], "routes": routes, "unverified_variant_rejected": True}


async def automatic(hass, entry):
    """Real HA timer fires with a logical topology clock; no manual refresh."""
    coordinator = entry.runtime_data
    records = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert not records or all(record.disabled_by is not None for record in records)
    assert coordinator._listeners and coordinator._unsub_refresh is not None
    suffix = "all-disabled" if records else "zero-entities"
    identifier = f"automatic-{suffix}"
    await configure(
        hass,
        {
            "topology_payload": {
                "body": {
                    "homes": [
                        {"id": "automatic-home", "modules": [{"id": identifier, "type": "NXG"}]}
                    ]
                }
            },
            "status_payload": {
                "body": {
                    "home": {
                        "modules": [
                            {
                                "id": identifier,
                                "type": "NXG",
                                "is_raining": False,
                                "reachable": True,
                            }
                        ]
                    }
                }
            },
        },
    )
    before = (await configure(hass, {}))["requests"]
    try:
        with logical_time(coordinator.topology_attempted_at + 300):
            for _ in range(100):
                entity_id = er.async_get(hass).async_get_entity_id(
                    "binary_sensor", "velux_active", f"{identifier}_is_raining"
                )
                if entity_id and hass.states.get(entity_id) is not None:
                    break
                await asyncio.sleep(1)
            else:
                raise AssertionError("Native coordinator timer did not discover the new entity")
            assert hass.states.get(entity_id).state == "off"
            after = (await configure(hass, {}))["requests"]
            assert after[len(before) :] == [
                ["/api/homesdata", None],
                ["/api/homestatus", "automatic-home"],
            ]
            assert all(
                er.async_get(hass).async_get(record.entity_id).disabled_by == record.disabled_by
                for record in records
            )
            return {
                "mode": suffix,
                "entity_id": entity_id,
                "native_timer_discovered": True,
                "raw_protocol_requests": after[len(before) :],
                "manual_requests": 0,
            }
    finally:
        await configure(hass, {"reset_payloads": True})
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert not coordinator._listeners and coordinator._unsub_refresh is None


async def statistics(hass, entry):
    """Read pre-candidate samples; native compilation has a live positive control."""
    from datetime import UTC, datetime

    from homeassistant.components.recorder import get_instance
    from homeassistant.components.recorder.statistics import get_metadata, statistics_during_period
    from homeassistant.components.recorder.tasks import StatisticsTask
    from homeassistant.util import dt as dt_util

    identifiers = {
        "sensor.synthetic_legacy_lab_gateway_wifi_strength": (44, "dBm"),
        "sensor.synthetic_legacy_lab_switch_rf_strength": (64, "dBm"),
        "sensor.synthetic_legacy_lab_switch_battery_level": (3724, "mV"),
    }
    recorder = get_instance(hass)
    await recorder.async_block_till_done()
    metadata = await hass.async_add_executor_job(
        lambda: get_metadata(hass, statistic_ids=set(identifiers))
    )
    history = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        datetime(1970, 1, 1, tzinfo=UTC),
        None,
        set(identifiers),
        "hour",
        None,
        {"mean"},
    )
    for identifier, (value, unit) in identifiers.items():
        assert metadata[identifier][1]["unit_of_measurement"] == unit
        assert len(history[identifier]) == 1 and history[identifier][0]["mean"] == value
        state = hass.states.get(identifier)
        assert float(state.state) == value
        assert all(
            key not in state.attributes
            for key in ("unit_of_measurement", "device_class", "state_class")
        )
        record = er.async_get(hass).async_get(identifier)
        assert record.options["sensor"]["display_precision"] == 2
    assert (
        er.async_get(hass)
        .async_get("sensor.synthetic_legacy_lab_switch_battery_level")
        .options["sensor"]["unit_of_measurement"]
        == "V"
    )
    now = dt_util.utcnow()
    period = now.replace(minute=now.minute // 5 * 5, second=0, microsecond=0)
    recorder.queue_task(StatisticsTask(period, False))
    await recorder.async_block_till_done()
    raw = await hass.async_add_executor_job(
        statistics_during_period, hass, period, None, set(identifiers), "5minute", None, {"mean"}
    )
    assert not raw
    percent = er.async_get(hass).async_get_entity_id(
        "sensor", "velux_active", "lab-switch_battery_percent"
    )
    control = await hass.async_add_executor_job(
        statistics_during_period, hass, period, None, {percent}, "5minute", None, {"mean"}
    )
    assert len(control[percent]) == 1 and abs(control[percent][0]["mean"] - 82) < 0.00001
    after = await hass.async_add_executor_job(
        lambda: get_metadata(hass, statistic_ids=set(identifiers))
    )
    assert metadata == after
    return {
        "prior_hourly_samples_retained": 3,
        "prior_metadata_unchanged": True,
        "raw_new_samples": 0,
        "battery_percent_positive_control": True,
        "saved_unit_override_and_precision_retained": True,
    }


async def budgets(hass, entry):
    """Incoming protocol traces include rejected HTTP calls; no outcome counters."""
    from homeassistant.exceptions import HomeAssistantError

    coordinator = entry.runtime_data
    clock = coordinator.topology_attempted_at
    homes = ["budget-first", "budget-second"]
    topology = {
        "body": {
            "homes": [
                {"id": home, "modules": [{"id": f"budget-{index}", "type": "NXG"}]}
                for index, home in enumerate(homes)
            ]
        }
    }
    status = {
        home: {"body": {"home": {"modules": [{"id": f"budget-{index}", "is_raining": False}]}}}
        for index, home in enumerate(homes)
    }
    status["lab-home"] = {
        "body": {
            "home": {
                "modules": [
                    {"id": "lab-gateway", "is_raining": False},
                    {"id": "lab-window", "current_position": 7},
                    {"id": "lab-shutter", "current_position": 20},
                    {"id": "lab-switch", "battery_percent": 82},
                ]
            }
        }
    }
    await configure(hass, {"topology_payload": topology, "status_by_home": status})
    traces = []

    async def checked(expected, *, failure=False, concurrent=False):
        before = len((await configure(hass, {}))["requests"])
        if failure:
            try:
                await action(hass)
            except HomeAssistantError:
                pass
            else:
                raise AssertionError("Expected a controlled cloud action error")
        elif concurrent:
            await asyncio.gather(
                hass.services.async_call("velux_active", "refresh", {}, blocking=True),
                hass.services.async_call("velux_active", "refresh", {}, blocking=True),
            )
            await hass.async_block_till_done()
        else:
            await action(hass)
        requests = (await configure(hass, {}))["requests"][before:]
        assert requests == expected, {"expected": expected, "actual": requests}
        traces.append(requests)

    old_status = [["/api/homestatus", home.id] for home in coordinator.homes]
    pair = [["/api/homestatus", home] for home in homes]
    with logical_time(clock + 299):
        await checked(old_status)
    with logical_time(clock + 300):
        await checked([["/api/homesdata", None], *pair])
        # Same response ID from different homes must fail, including unsupported models.
        for model in ("NXG", "FUTURE"):
            contradictory = {
                home: {
                    "body": {
                        "home": {
                            "modules": [
                                {"id": "budget-0", "type": model, "is_raining": bool(index)}
                            ]
                        }
                    }
                }
                for index, home in enumerate(homes)
            }
            await configure(hass, {"status_by_home": contradictory})
            await checked(pair, failure=True)
            assert not coordinator.last_update_success
            await configure(hass, {"status_by_home": status})
            await checked(pair)
        await configure(hass, {"status_delay": 0.2})
        await checked(pair, concurrent=True)
        await configure(hass, {"status_delay": 0})
        await configure(hass, {"invalidate_access": True})
        await checked([pair[0], ["/oauth2/token", "refresh_token"], *pair])
        await configure(hass, {"invalidate_access": True, "reject_refresh": True})
        await checked(
            [pair[0], ["/oauth2/token", "refresh_token"], ["/oauth2/token", "password"], *pair]
        )
        await configure(hass, {"reject_refresh": False, "outage": 429})
        await checked([pair[0]], failure=True)
        await checked([], failure=True)
        # Direct public endpoint calls supplement the action and prove one global deadline.
        before_blocked = list((await configure(hass, {}))["requests"])
        for operation in (
            coordinator.api.get_home_data(),
            coordinator.api.get_home_statuses(coordinator.homes[1]),
            coordinator.api.authenticate(entry.data["username"], entry.data["password"]),
            coordinator.api.refresh_access_token(coordinator.api.auth_token),
        ):
            try:
                await operation
            except HomeAssistantError:
                raise AssertionError(
                    "Client should expose its own controlled rate-limit error"
                ) from None
            except Exception as error:
                assert type(error).__name__ == "RateLimitError"
            else:
                raise AssertionError("Global deadline was bypassed")
        assert (await configure(hass, {}))["requests"] == before_blocked
    await configure(hass, {"outage": 0, "topology_outage": 503})
    with logical_time(clock + 600):
        await checked([["/api/homesdata", None], *pair])
    with logical_time(clock + 899):
        await checked(pair)
    with logical_time(clock + 900):
        await checked([["/api/homesdata", None], *pair])
    # Ordinary long numeric limits and HTTP dates must survive native manual calls.
    await configure(hass, {"topology_outage": 0, "outage": 429, "retry_after": "99999"})
    with logical_time(clock + 900):
        await checked([pair[0]], failure=True)
    await configure(hass, {"outage": 0})
    for elapsed in (4501, 100898):
        with logical_time(clock + elapsed):
            await checked([], failure=True)
    with logical_time(clock + 100899):
        # A blocked topology attempt just before expiry still counts as an
        # attempt for the cadence; status can recover without bypassing it.
        await checked(pair)
    with logical_time(clock + 101198):
        await checked([["/api/homesdata", None], *pair])
    from datetime import UTC, datetime, timedelta
    from email.utils import format_datetime

    await configure(
        hass,
        {"outage": 429, "retry_after": format_datetime(datetime.now(UTC) + timedelta(hours=2))},
    )
    with logical_time(clock + 101198):
        await checked([pair[0]], failure=True)
        date_deadline = coordinator.api._retry_at
    await configure(hass, {"outage": 0})
    with logical_time(clock + 101259):
        await checked([], failure=True)
    with logical_time(date_deadline - 0.001):
        await checked([], failure=True)
    with logical_time(date_deadline):
        await checked(pair)
    with logical_time(date_deadline + 300):
        await checked([["/api/homesdata", None], *pair])
    return {
        "raw_protocol_batches": traces,
        "multi_home_cadence": True,
        "concurrent_manual_coalesced": True,
        "one_401_replay": True,
        "one_rejected_renewal_then_credential_fallback": True,
        "global_429_no_http": True,
        "account_wide_duplicates_rejected": True,
        "numeric_99999_full_deadline": True,
        "http_date_two_hour_full_deadline": True,
        "requires_process_restart": True,
    }
