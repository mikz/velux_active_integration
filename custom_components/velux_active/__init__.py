"""The velux_active integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import api
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.COVER, Platform.SENSOR, Platform.BINARY_SENSOR]

# TODO Create ConfigEntry type alias with ConfigEntryAuth or AsyncConfigEntryAuth object
# TODO Rename type alias and update all entry annotations
type VeluxActiveConfigEntry = ConfigEntry[api.AsyncConfigEntryAuth]

# # TODO Update entry annotation
async def async_setup_entry(hass: HomeAssistant, entry: VeluxActiveConfigEntry) -> bool:
    """Set up velux_active from a config entry."""

    domain = hass.data.setdefault(DOMAIN, {})

    api_client = api.VeluxActiveAPI(aiohttp_client.async_get_clientsession(hass))

    async def async_update_data():
        """Fetch data from API."""
        try:
            homes = await api_client.get_home_data()
            data = {}
            for home in homes:
                statuses = await api_client.get_home_statuses(home)
                devices = []
                for status in statuses:
                    device = _convert_status_to_sensor(status)
                    if device is not None:
                        devices.append(device)
                data[home] = {"devices": devices}
            return data
        except api.InvalidAuthError as err:
            await api_client.authenticate(entry.data["username"], entry.data["password"])
            _LOGGER.error("Re-authenticated with Velux Active because of %s", err)
            raise UpdateFailed(f"Re-authenticated with Velux Active because of {err}") from err
        except Exception as err:
            _LOGGER.error(err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="velux_active",
        update_method=async_update_data,
        update_interval=timedelta(minutes=1),
    )

    await api_client.authenticate(entry.data["username"], entry.data["password"])
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = api_client

    domain["coordinator"] = coordinator
    domain["api_client"] = api_client
    domain["homes"] = list(coordinator.data.keys())

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

def _convert_status_to_sensor(status) -> dict:
    _LOGGER.info("CONVERT: %s %s", status, status.type)

    match status.type:
        case 'NXG':
            return api.VeluxGatewayData(**status)
        case 'NXS':
            _LOGGER.info("SENSOR: %s", status)
            return api.VeluxSwitchData(**status)
        case 'NXO':
            match status['velux_type']:
                case 'shutter':
                    return api.VeluxShutterData(**status)
                case 'window':
                    return api.VeluxWindowData(**status)
                case _:
                    _LOGGER.debug("UNKNOWN OBJECT: %s", status)
                    return None
        case _:
            _LOGGER.debug("UNKNOWN TYPE: %s", status.type)
            return None

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Velux Active config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
