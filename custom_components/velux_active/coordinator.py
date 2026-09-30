"""Shared one-minute cloud polling and authentication lifecycle."""

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import aiohttp_client
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
        self._manual_task: asyncio.Task | None = None
        self._device_reachability: dict[str, bool] = {}
        self._device_log_labels: dict[str, int] = {}

    async def _async_manual_update(self) -> tuple[bool, Exception | None]:
        """Capture this operation's result before a later poll can change it."""
        await self.async_refresh()
        return self.last_update_success, self.last_exception

    async def async_manual_refresh(self) -> tuple[bool, Exception | None]:
        """Share entry-owned work; cancellation of a waiter leaves it running."""
        if self._manual_task is None or self._manual_task.done():
            self._manual_task = self.config_entry.async_create_background_task(
                self.hass,
                self._async_manual_update(),
                "VELUX ACTIVE manual refresh",
                eager_start=False,
            )
        operation = self._manual_task
        try:
            return await asyncio.shield(operation)
        except asyncio.CancelledError:
            if operation.cancelled():
                raise HomeAssistantError("VELUX ACTIVE was unloaded during refresh") from None
            raise

    def _log_device_transitions(self, data: dict) -> None:
        """Emit one anonymous device transition, regardless of entity count."""
        for home in data.values():
            for device in home["devices"]:
                reachable = getattr(device, "reachable", None)
                if reachable is None:
                    continue
                previous = self._device_reachability.get(device.id)
                self._device_reachability[device.id] = reachable
                label = self._device_log_labels.setdefault(
                    device.id, len(self._device_log_labels) + 1
                )
                if reachable is False and previous is not False:
                    _LOGGER.info("VELUX device %s is unavailable", label)
                elif reachable is True and previous is False:
                    _LOGGER.info("VELUX device %s recovered", label)

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
            self._log_device_transitions(data)
            return data
        except InvalidAuthError as err:
            raise ConfigEntryAuthFailed("VELUX login must be renewed") from err
        except RateLimitError as err:
            raise UpdateFailed(str(err), retry_after=err.retry_after) from err
        except APIConnectionError as err:
            raise UpdateFailed(str(err)) from err


type VeluxActiveConfigEntry = ConfigEntry[VeluxCoordinator]
