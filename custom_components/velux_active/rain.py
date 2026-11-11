"""Explicit, single-attempt rain ventilation; ordinary covers remain observational."""

import base64
import hashlib
import hmac
import time
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er

from .api import APIConnectionError, VeluxGatewayData, VeluxWindowData
from .const import DOMAIN
from .coordinator import VeluxActiveConfigEntry
from .velux_active_client.client import JSON


def signed_window(device: VeluxWindowData, position: int, keys: dict[str, Any]) -> dict[str, JSON]:
    """Sign the VELUX force command; protocol documented by Niek/ha-velux-active."""
    key = base64.b64decode(keys["hash_sign_key"], altchars=b"-_", validate=True)
    # Nanoseconds provide distinct nonces across calls and process restarts.
    now = time.time_ns()
    timestamp, nonce = divmod(now, 1_000_000_000)
    message = f"target_position{position}{timestamp}{nonce}{device.id}"
    signature = base64.urlsafe_b64encode(
        hmac.new(key, message.encode(), hashlib.sha512).digest()
    ).decode()
    return {
        "id": device.id,
        "bridge": device.bridge,
        "sign_key_id": keys["sign_key_id"],
        "target_position": position,
        "force": True,
        "timestamp": timestamp,
        "nonce": nonce,
        "hash_target_position": signature,
    }


def async_register_rain_service(hass: HomeAssistant) -> None:
    """Register the opt-in command separately from ordinary cover control."""

    async def handle(call: ServiceCall) -> None:
        registry = er.async_get(hass)
        entity = registry.async_get(call.data["entity_id"])
        if entity is None or entity.platform != DOMAIN or not entity.config_entry_id:
            raise ServiceValidationError("Select a VELUX cloud window")
        entry: VeluxActiveConfigEntry | None = hass.config_entries.async_get_entry(
            entity.config_entry_id
        )
        if entry is None or entry.state.value != "loaded":
            raise ServiceValidationError("The VELUX cloud account is not loaded")
        keys = dict(entry.options)
        if not all(keys.get(key) for key in ("hash_sign_key", "sign_key_id", "gateway_id")):
            raise ServiceValidationError("Pair the VELUX gateway before rain ventilation")
        coordinator = entry.runtime_data
        success, _ = await coordinator.async_manual_refresh()
        if not success or entry.runtime_data is not coordinator or entry.state.value != "loaded":
            raise HomeAssistantError("Cannot verify the current VELUX cloud state")
        devices = [device for home in coordinator.data.values() for device in home["devices"]]
        window = next((d for d in devices if d.id == entity.unique_id), None)
        gateway = next((d for d in devices if d.id == keys["gateway_id"]), None)
        if (
            not isinstance(window, VeluxWindowData)
            or window.reachable is not True
            or window.bridge != keys["gateway_id"]
            or not isinstance(gateway, VeluxGatewayData)
            or window.home.id != gateway.home.id
            or gateway.is_raining is not True
            or gateway.reachable is False
        ):
            raise ServiceValidationError("A reachable paired window and reported rain are required")
        try:
            module = signed_window(window, call.data["position"], keys)
            await coordinator.api.set_state({"id": window.home.id, "modules": [module]})
        except (APIConnectionError, ValueError, KeyError) as err:
            raise HomeAssistantError("VELUX rain ventilation was not confirmed") from err
        # No optimistic position, retry, or timer renewal: firmware owns the 15-minute close.
        await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        "open_during_rain",
        handle,
        schema=vol.Schema(
            {
                vol.Required("entity_id"): cv.entity_id,
                vol.Required("position"): vol.All(vol.Coerce(int), vol.Range(min=1, max=50)),
            }
        ),
    )
