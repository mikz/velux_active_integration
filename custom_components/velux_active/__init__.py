"""Set up VELUX ACTIVE cloud sensors and its refresh action."""

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .api import VeluxGatewayData, VeluxShutterData, VeluxWindowData
from .const import DOMAIN
from .coordinator import VeluxActiveConfigEntry, VeluxCoordinator

PLATFORMS = [Platform.COVER, Platform.SENSOR, Platform.BINARY_SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
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
    gateways: dict[str, str] = {}
    for device in sorted(devices, key=lambda device: device.type != "NXG"):
        cover = device if isinstance(device, (VeluxWindowData, VeluxShutterData)) else None
        model = (cover.velux_type if cover else None) or device.type
        name = device.name if isinstance(device, VeluxGatewayData) else None
        bridge = None if isinstance(device, VeluxGatewayData) else device.bridge
        registered = registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, device.id)},
            name=name or f"{model.capitalize()} {device.id[-4:]}",
            manufacturer=(cover.manufacturer if cover else None) or "Velux",
            model=model,
            via_device_id=gateways.get(bridge) if bridge is not None else None,
        )
        if device.type == "NXG":
            gateways[device.id] = registered.id
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: VeluxActiveConfigEntry) -> bool:
    """Unload entities; HA shuts down entry-owned coordinator subscriptions."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
