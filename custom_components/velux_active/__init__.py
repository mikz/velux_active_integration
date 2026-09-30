"""Set up VELUX ACTIVE cloud sensors and its refresh action."""

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import VeluxActiveConfigEntry, VeluxCoordinator

PLATFORMS = [Platform.COVER, Platform.SENSOR, Platform.BINARY_SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register the zero-argument action independently of entry loading."""

    async def async_handle_refresh(call: ServiceCall) -> None:
        entries = hass.config_entries.async_entries(DOMAIN)
        entry = next((entry for entry in entries if entry.state is ConfigEntryState.LOADED), None)
        if entry is None:
            raise ServiceValidationError("No VELUX ACTIVE account is loaded")
        coordinator = entry.runtime_data
        success, error = await coordinator.async_manual_refresh()
        if entry.state is not ConfigEntryState.LOADED or entry.runtime_data is not coordinator:
            raise ServiceValidationError("VELUX ACTIVE was unloaded during refresh")
        if not success:
            raise HomeAssistantError("VELUX ACTIVE cloud refresh failed") from error

    hass.services.async_register(DOMAIN, "refresh", async_handle_refresh, schema=vol.Schema({}))
    return True


async def async_setup_entry(hass: HomeAssistant, entry: VeluxActiveConfigEntry) -> bool:
    """Load an existing username/password entry without changing entity identities."""
    coordinator = VeluxCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    registry = dr.async_get(hass)
    devices = [device for home in coordinator.data.values() for device in home["devices"]]
    gateways = {}
    for device in sorted(devices, key=lambda device: device.type != "NXG"):
        model = getattr(device, "velux_type", device.type)
        info = {
            "identifiers": {(DOMAIN, device.id)},
            "name": getattr(device, "name", None) or f"{model.capitalize()} {device.id[-4:]}",
            "manufacturer": getattr(device, "manufacturer", None) or "Velux",
            "model": model,
        }
        bridge = getattr(device, "bridge", None)
        if bridge in gateways:
            info["via_device_id"] = gateways[bridge]
        registered = registry.async_get_or_create(config_entry_id=entry.entry_id, **info)
        if device.type == "NXG":
            gateways[device.id] = registered.id
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: VeluxActiveConfigEntry) -> bool:
    """Unload entities; HA shuts down entry-owned coordinator subscriptions."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
