"""Set up VELUX ACTIVE cloud sensors and its refresh action."""

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import ConfigType

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
            raise ServiceValidationError(
                "No VELUX ACTIVE account is loaded",
                translation_domain=DOMAIN,
                translation_key="not_loaded",
            )
        coordinator = entry.runtime_data
        success, error = await coordinator.async_manual_refresh()
        if entry.state is not ConfigEntryState.LOADED or entry.runtime_data is not coordinator:
            raise ServiceValidationError(
                "VELUX ACTIVE was unloaded during refresh",
                translation_domain=DOMAIN,
                translation_key="unloaded",
            )
        if not success:
            raise HomeAssistantError(
                "VELUX ACTIVE cloud refresh failed",
                translation_domain=DOMAIN,
                translation_key="refresh_failed",
            ) from error

    hass.services.async_register(DOMAIN, "refresh", async_handle_refresh, schema=vol.Schema({}))
    return True


async def async_setup_entry(hass: HomeAssistant, entry: VeluxActiveConfigEntry) -> bool:
    """Load an existing username/password entry without changing entity identities."""
    coordinator = VeluxCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    coordinator.async_register_devices()
    entry.async_on_unload(coordinator.async_add_listener(coordinator.async_register_devices))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: VeluxActiveConfigEntry) -> bool:
    """Unload entities; HA shuts down entry-owned coordinator subscriptions."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: VeluxActiveConfigEntry, device: dr.AnyDeviceEntry
) -> bool:
    """Return permission; Home Assistant owns registry and association deletion."""
    if entry.state is not ConfigEntryState.LOADED or device.config_entry_id != entry.entry_id:
        return False
    identifiers = [identifier for domain, identifier in device.identifiers if domain == DOMAIN]
    return len(identifiers) == 1 and entry.runtime_data.async_can_remove_device(identifiers[0])
