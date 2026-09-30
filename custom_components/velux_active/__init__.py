"""Set up VELUX ACTIVE cloud sensors."""

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    APIConnectionError,
    InvalidAuthError,
    RateLimitError,
    VeluxActiveAPI,
    device_from_module,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.COVER, Platform.SENSOR, Platform.BINARY_SENSOR]
type VeluxActiveConfigEntry = ConfigEntry[VeluxCoordinator]


class VeluxCoordinator(DataUpdateCoordinator):
    """Poll status once per minute and let HA handle retries and reauthentication."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(minutes=1),
        )
        self.api = VeluxActiveAPI(aiohttp_client.async_get_clientsession(hass))
        self.homes = None

    async def _async_update_data(self):
        try:
            if self.api.auth_token is None:
                await self.api.authenticate(
                    self.config_entry.data["username"], self.config_entry.data["password"]
                )
            if self.homes is None:
                self.homes = await self.api.get_home_data()
            data = {}
            for home in self.homes:
                modules = await self.api.get_home_statuses(home)
                data[home] = {
                    "devices": [
                        device
                        for module in modules
                        if (device := device_from_module(module)) is not None
                    ]
                }
            return data
        except InvalidAuthError as err:
            raise ConfigEntryAuthFailed("VELUX login must be renewed") from err
        except RateLimitError as err:
            raise UpdateFailed(str(err), retry_after=err.retry_after) from err
        except APIConnectionError as err:
            raise UpdateFailed(str(err)) from err


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

    async def async_handle_refresh(call: ServiceCall) -> None:
        await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, "refresh", async_handle_refresh)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload platforms and remove the refresh action."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    hass.services.async_remove(DOMAIN, "refresh")
    return True
