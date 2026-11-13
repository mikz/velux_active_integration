"""Paired cloud covers use native HA actions without household policy."""

import base64
import hashlib
import hmac
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from aiohttp import ClientSession, web
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from custom_components.velux_active.api import (
    APIConnectionError,
    AuthToken,
    InvalidAuthError,
    VeluxActiveAPI,
)
from custom_components.velux_active.velux_active_client.pairing import SigningKey
from tests.integration.test_quality import loaded as loaded

KEYS = {
    "hash_sign_key": base64.urlsafe_b64encode(bytes(range(32))).decode(),
    "sign_key_id": "synthetic-key-id",
    "gateway_id": "gateway-1",
}


async def command(hass, entity_id, position=12):
    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {"entity_id": entity_id, "position": position},
        blocking=True,
    )


def window_id(hass, entry):
    return next(
        e.entity_id
        for e in er.async_get(hass).entities.values()
        if e.config_entry_id == entry.entry_id and e.entity_id.startswith("cover.window")
    )


@pytest.mark.parametrize("rain", [True, False, None])
async def test_cover_command_signed_once_without_rain_policy(hass, loaded, rain):
    entry, simulator, api = loaded
    gateway = next(
        d for h in entry.runtime_data.data.values() for d in h["devices"] if d.type == "NXG"
    )
    keys = {**KEYS, "gateway_id": gateway.id}
    hass.config_entries.async_update_entry(entry, options=keys)
    simulator.state["rain"] = rain
    simulator.state["omit_rain"] = rain is None
    entity_id = window_id(hass, entry)
    with patch.object(api, "set_state", new_callable=AsyncMock) as send:
        await command(hass, entity_id)
    send.assert_awaited_once()
    home = send.call_args.args[0]
    module = home["modules"][0]
    message = f"target_position12{module['timestamp']}{module['nonce']}{module['id']}"
    expected = base64.urlsafe_b64encode(
        hmac.new(bytes(range(32)), message.encode(), hashlib.sha512).digest()
    ).decode()
    assert module["hash_target_position"] == expected
    assert module["bridge"] == gateway.id and module["force"] is True
    assert hass.states.get(entity_id).attributes["current_position"] == 7


@pytest.mark.parametrize(
    "case",
    [
        "no_keys",
        "wrong_gateway",
        "unreachable",
        "outage",
        "shutter",
        "bad_key",
        "rejected",
    ],
)
async def test_cover_command_rejects_unverified_or_invalid_input(hass, loaded, case):
    entry, simulator, api = loaded
    gateway = next(
        d for h in entry.runtime_data.data.values() for d in h["devices"] if d.type == "NXG"
    )
    keys = {**KEYS, "gateway_id": gateway.id}
    simulator.state["rain"] = case != "dry"
    if case == "no_keys":
        keys = {}
    if case == "wrong_gateway":
        keys["gateway_id"] = "another-gateway"
    if case == "bad_key":
        keys["hash_sign_key"] = "%%%"
    if case == "outage":
        simulator.state["outage"] = 503
    if case == "unreachable":
        simulator.state["reachable"] = False
    hass.config_entries.async_update_entry(entry, options=keys)
    entity_id = window_id(hass, entry)
    if case == "shutter":
        entity_id = next(
            e.entity_id
            for e in er.async_get(hass).entities.values()
            if e.config_entry_id == entry.entry_id and e.entity_id.startswith("cover.shutter")
        )
    with patch.object(api, "set_state", new_callable=AsyncMock) as send:
        if case == "rejected":
            send.side_effect = APIConnectionError("synthetic")
        with pytest.raises(HomeAssistantError):
            await command(hass, entity_id)
    assert send.await_count == (1 if case == "rejected" else 0)


async def test_pairing_options_save_secrets_only_after_button(hass, loaded):
    entry, _, api = loaded
    gateway = next(
        d for h in entry.runtime_data.data.values() for d in h["devices"] if d.type == "NXG"
    )
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"
    with patch.object(api, "set_state", new_callable=AsyncMock) as send:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"gateway_id": gateway.id, "gateway_host": "synthetic.invalid"}
        )
    assert result["step_id"] == "pair_button" and not entry.options
    assert send.call_args.args[0]["modules"] == [{"id": gateway.id, "retrieve_key": True}]
    key = SigningKey(KEYS["sign_key_id"], KEYS["hash_sign_key"])
    with patch(
        "custom_components.velux_active.pairing_flow.retrieve_signing_key", return_value=key
    ):
        result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] == "create_entry"
    assert dict(entry.options) == {**KEYS, "gateway_id": gateway.id}
    assert KEYS["hash_sign_key"] not in repr(key)


@pytest.mark.parametrize(
    "payload",
    [{"status": "ok"}, {"status": "ok", "body": {"errors": [{"code": 42}]}}, {"status": "error"}],
)
async def test_command_http_checks_product_errors_without_retry(
    aiohttp_server, socket_enabled, payload
):
    calls = []

    async def handle(request):
        calls.append(await request.json())
        assert request.headers["Authorization"] == "Bearer synthetic"
        return web.json_response(payload)

    app = web.Application()
    app.router.add_post("/syncapi/v1/setstate", handle)
    server = await aiohttp_server(app)
    async with ClientSession() as session:
        api = VeluxActiveAPI(session, base_url=str(server.make_url("")))
        api.auth_token = AuthToken("synthetic", "refresh", 3600)
        if payload == {"status": "ok"}:
            await api.set_state({"id": "home", "modules": []})
        else:
            with pytest.raises(APIConnectionError):
                await api.set_state({"id": "home", "modules": []})
    assert calls == [{"home": {"id": "home", "modules": []}}]


async def test_native_open_close_and_no_rain_service(hass, loaded):
    entry, _, api = loaded
    gateway = next(
        d for h in entry.runtime_data.data.values() for d in h["devices"] if d.type == "NXG"
    )
    hass.config_entries.async_update_entry(entry, options={**KEYS, "gateway_id": gateway.id})
    entity_id = window_id(hass, entry)
    assert not hass.services.has_service("velux_active", "open_during_rain")
    with patch.object(api, "set_state", new_callable=AsyncMock) as send:
        for service, position in [("open_cover", 100), ("close_cover", 0)]:
            await hass.services.async_call(
                "cover", service, {"entity_id": entity_id}, blocking=True
            )
            assert send.call_args.args[0]["modules"][0]["target_position"] == position
    assert send.await_count == 2


async def test_unload_during_command_refresh(hass, loaded):
    entry, _, api = loaded
    gateway = next(
        d for h in entry.runtime_data.data.values() for d in h["devices"] if d.type == "NXG"
    )
    hass.config_entries.async_update_entry(entry, options={**KEYS, "gateway_id": gateway.id})
    entity_id = window_id(hass, entry)
    cover = hass.data["cover"].get_entity(entity_id)

    async def unload():
        await hass.config_entries.async_unload(entry.entry_id)
        return True, None

    with (
        patch.object(entry.runtime_data, "async_manual_refresh", side_effect=unload),
        patch.object(api, "set_state", new_callable=AsyncMock) as send,
    ):
        with pytest.raises(HomeAssistantError, match="Cannot verify"):
            await cover.async_set_cover_position(position=12)
    send.assert_not_awaited()
    with pytest.raises(HomeAssistantError, match="not loaded"):
        await cover.async_set_cover_position(position=12)


async def test_pairing_rejects_unloaded_account(hass, loaded):
    entry, _, _ = loaded
    await hass.config_entries.async_unload(entry.entry_id)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "abort" and result["reason"] == "not_loaded"


@pytest.mark.parametrize(
    ("exception", "error"),
    [(APIConnectionError, "pairing_failed"), (InvalidAuthError, "invalid_auth")],
)
async def test_pairing_errors_preserve_previous_keys(hass, loaded, exception, error):
    from custom_components.velux_active.velux_active_client.pairing import VeluxPairingError

    entry, _, api = loaded
    hass.config_entries.async_update_entry(entry, options=KEYS)
    gateway = next(
        d for h in entry.runtime_data.data.values() for d in h["devices"] if d.type == "NXG"
    )
    result = await hass.config_entries.options.async_init(entry.entry_id)
    previous = entry.runtime_data.data
    entry.runtime_data.data = {}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"gateway_id": gateway.id, "gateway_host": "synthetic.invalid"}
    )
    entry.runtime_data.data = previous
    assert result["errors"] == {"base": "pairing_failed"}
    result = await hass.config_entries.options.async_configure(result["flow_id"], None)
    with patch.object(api, "set_state", side_effect=exception("synthetic")) as send:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"gateway_id": gateway.id, "gateway_host": "synthetic.invalid"}
        )
    send.assert_awaited_once()
    assert result["step_id"] == "init" and result["errors"] == {"base": error}
    assert dict(entry.options) == KEYS
    with patch.object(api, "set_state", new_callable=AsyncMock):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"gateway_id": gateway.id, "gateway_host": "synthetic.invalid"}
        )
    with patch(
        "custom_components.velux_active.pairing_flow.retrieve_signing_key",
        side_effect=VeluxPairingError("synthetic"),
    ):
        result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["step_id"] == "pair_button" and result["errors"] == {"base": "pairing_failed"}
    assert dict(entry.options) == KEYS
    hass.config_entries.options.async_abort(result["flow_id"])


@pytest.mark.parametrize("position", [101, -1, "invalid"])
async def test_cover_action_rejects_out_of_bounds_before_cloud(hass, loaded, position):
    entry, _, api = loaded
    with patch.object(api, "set_state", new_callable=AsyncMock) as send:
        with pytest.raises(vol.Invalid):
            await command(hass, window_id(hass, entry), position)
    send.assert_not_awaited()
