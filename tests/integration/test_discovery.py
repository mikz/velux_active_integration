"""Synthetic raw HomeKit TXT routes only to a cloud-account confirmation hint."""

from ipaddress import IPv4Address
from unittest.mock import Mock, patch

import pytest
from homeassistant import loader
from homeassistant.components.zeroconf.discovery import (
    ZeroconfDiscovery,
    async_get_homekit_discovery,
    build_homekit_model_lookups,
    info_from_service,
)
from homeassistant.config_entries import SOURCE_HOMEKIT, ConfigEntryDisabler
from pytest_homeassistant_custom_component.common import MockConfigEntry
from zeroconf.asyncio import AsyncServiceInfo

from custom_components.velux_active.const import DOMAIN
from tests.lab.cloud import PASSWORD, USERNAME


def advertisement(model=b"VELUX Gateway\x00", *, host="192.0.2.10", port=12345, paired=False):
    properties = {b"sf": b"0" if paired else b"1"}
    if model is not None:
        properties[b"md"] = model
    return AsyncServiceInfo(
        "_hap._tcp.local.",
        "Synthetic VELUX._hap._tcp.local.",
        server="synthetic.local.",
        addresses=[IPv4Address(host).packed],
        port=port,
        properties=properties,
    )


@pytest.mark.parametrize("model", [b"VELUX Gateway", b"VELUX Gateway\x00"])
@pytest.mark.parametrize("paired", [False, True])
async def test_raw_homekit_txt_native_match_and_cloud_confirmation_preserve_local_routing(
    hass, model, paired
):
    models, matchers = build_homekit_model_lookups(await loader.async_get_homekit(hass))
    info = info_from_service(advertisement(model, paired=paired))
    assert info.properties["md"] == model.decode()
    match = async_get_homekit_discovery(models, matchers, info.properties)
    assert match.domain == DOMAIN
    assert match.always_discover  # Native router continues to HomeKit Device for unpaired too.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HOMEKIT}, data=info
    )
    assert result["step_id"] == "discovery_confirm"
    assert result["data_schema"]({}) == {}


@pytest.mark.parametrize(
    "model",
    [
        None,
        b"",
        b"Other",
        b"VELUX Gateway-evil",
        b"VELUX Gateway Pro",
        b"VELUX Gatewayx",
        b"VELUX Gatewa[y]",
        b"VELUX Gateway\x00suffix",
        b"VELUX\x00 Gateway",
        b"VELUX Gateway\x00\x00",
    ],
)
async def test_unverified_advertisement_cannot_start_cloud_hint(hass, model):
    models, matchers = build_homekit_model_lookups(await loader.async_get_homekit(hass))
    info = info_from_service(advertisement(model))
    assert async_get_homekit_discovery(models, matchers, info.properties) is None
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HOMEKIT}, data=info
    )
    assert result["type"] == "abort" and result["reason"] == "not_supported"


async def test_discovery_confirmation_login_failure_recovery_and_no_lan_account_binding(
    hass, cloud
):
    simulator, api = cloud
    info = info_from_service(advertisement())
    with (
        patch("custom_components.velux_active.config_flow.VeluxActiveAPI", return_value=api),
        patch("custom_components.velux_active.coordinator.VeluxActiveAPI", return_value=api),
    ):
        confirm = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_HOMEKIT}, data=info
        )
        login = await hass.config_entries.flow.async_configure(confirm["flow_id"], {})
        assert login["step_id"] == "user"
        failed = await hass.config_entries.flow.async_configure(
            login["flow_id"], {"username": USERNAME, "password": "wrong"}
        )
        assert failed["errors"] == {"base": "invalid_auth"}
        result = await hass.config_entries.flow.async_configure(
            login["flow_id"], {"username": USERNAME, "password": PASSWORD}
        )
        assert result["type"] == "create_entry"
        await hass.async_block_till_done()
        entry = result["result"]
        assert entry.unique_id is None
        assert entry.data == {"username": USERNAME, "password": PASSWORD}
        assert all(
            path in ("/oauth2/token", "/api/homesdata", "/api/homestatus")
            for path, _ in simulator.requests
        )
        assert info.host not in api._base_url
        changed = info_from_service(advertisement(host="192.0.2.20", port=54321))
        before = dict(entry.data)
        rediscovered = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_HOMEKIT}, data=changed
        )
        assert rediscovered["reason"] == "single_instance_allowed"
        assert entry.data == before and entry.unique_id is None


async def test_discovery_dedup_manual_race_and_disabled_existing_entry(hass):
    info = info_from_service(advertisement())
    manual = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    discovered = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HOMEKIT}, data=info
    )
    assert discovered["reason"] == "already_in_progress"
    hass.config_entries.flow.async_abort(manual["flow_id"])
    first = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HOMEKIT}, data=info
    )
    second = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HOMEKIT}, data=info
    )
    assert second["reason"] == "already_in_progress"
    hass.config_entries.flow.async_abort(first["flow_id"])
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": USERNAME, "password": PASSWORD},
        disabled_by=ConfigEntryDisabler.USER,
    )
    entry.add_to_hass(hass)
    before = dict(entry.data)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HOMEKIT}, data=info
    )
    assert result["reason"] == "single_instance_allowed"
    assert entry.data == before and entry.disabled_by is ConfigEntryDisabler.USER


@pytest.mark.parametrize("paired", [False, True])
async def test_native_raw_dispatch_keeps_homekit_device_route(hass, paired):
    models, matchers = build_homekit_model_lookups(await loader.async_get_homekit(hass))
    zeroconf_types = await loader.async_get_zeroconf(hass)
    service = advertisement(paired=paired)
    discovery = ZeroconfDiscovery(hass, Mock(), zeroconf_types, models, matchers, service)
    with patch(
        "homeassistant.components.zeroconf.discovery.discovery_flow.async_create_flow"
    ) as dispatch:
        discovery._async_process_service_update(service, service.type, service.name)
    domains = {call.args[1] for call in dispatch.call_args_list}
    assert DOMAIN in domains
    assert "homekit_controller" in domains


@pytest.mark.parametrize("malformed", ["wrong_service", "non_text_model"])
async def test_flow_rejects_crafted_discovery_shape(hass, malformed):
    info = info_from_service(advertisement())
    if malformed == "wrong_service":
        info.type = "_other._tcp.local."
    else:
        info.properties["md"] = {"untrusted": "provider"}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HOMEKIT}, data=info
    )
    assert result["reason"] == "not_supported"


async def test_simultaneous_discovery_and_manual_credentials_create_one_account(hass, cloud):
    """Native completion ends a sibling flow, including an in-flight configure call."""
    import asyncio

    from homeassistant.config_entries import ConfigEntryState
    from homeassistant.data_entry_flow import UnknownFlow

    _, api = cloud
    entered = asyncio.Event()
    release = asyncio.Event()
    arrivals = 0
    original = api.authenticate

    async def delayed(username, password):
        nonlocal arrivals
        arrivals += 1
        if arrivals == 2:
            entered.set()
        await release.wait()
        return await original(username, password)

    with (
        patch("custom_components.velux_active.config_flow.VeluxActiveAPI", return_value=api),
        patch("custom_components.velux_active.coordinator.VeluxActiveAPI", return_value=api),
    ):
        discovery = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_HOMEKIT}, data=info_from_service(advertisement())
        )
        discovery = await hass.config_entries.flow.async_configure(discovery["flow_id"], {})
        manual = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        with patch.object(api, "authenticate", side_effect=delayed):
            tasks = [
                asyncio.create_task(
                    hass.config_entries.flow.async_configure(
                        flow["flow_id"], {"username": USERNAME, "password": PASSWORD}
                    )
                )
                for flow in (discovery, manual)
            ]
            await entered.wait()
            release.set()
            results = await asyncio.gather(*tasks, return_exceptions=True)
        assert sum(isinstance(result, UnknownFlow) for result in results) == 1
        created = [result for result in results if isinstance(result, dict)]
        assert len(created) == 1 and created[0]["type"] == "create_entry"
        await hass.async_block_till_done()
        entries = hass.config_entries.async_entries(DOMAIN)
        assert len(entries) == 1 and entries[0].state is ConfigEntryState.LOADED
        assert entries[0].unique_id is None
        assert entries[0].data == {"username": USERNAME, "password": PASSWORD}
        assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)
