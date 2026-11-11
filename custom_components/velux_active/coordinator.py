"""Shared one-minute cloud polling and authentication lifecycle."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from time import monotonic
from typing import TypedDict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    APIConnectionError,
    InvalidAuthError,
    RateLimitError,
    VeluxActiveAPI,
    VeluxDevice,
    VeluxGatewayData,
    VeluxHome,
    VeluxShutterData,
    VeluxWindowData,
    device_from_module,
)
from .const import DOMAIN, async_rate_limit_state

_LOGGER = logging.getLogger(__name__)


class HomeSnapshot(TypedDict):
    """Accepted status observations for one known home."""

    devices: list[VeluxDevice]


type VeluxSnapshot = dict[VeluxHome, HomeSnapshot]
type ManualResult = tuple[bool, BaseException | None]


class VeluxCoordinator(DataUpdateCoordinator[VeluxSnapshot]):
    """Poll status once per minute and let HA handle retries and reauthentication."""

    def __init__(self, hass: HomeAssistant, entry: VeluxActiveConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(minutes=1),
        )
        self.api = VeluxActiveAPI(
            aiohttp_client.async_get_clientsession(hass),
            rate_limit_state=async_rate_limit_state(hass),
        )
        self._entry = entry
        self.homes: list[VeluxHome] | None = None
        self._manual_task: asyncio.Task[ManualResult] | None = None
        self._device_reachability: dict[str, bool] = {}
        self._device_log_labels: dict[str, int] = {}
        self.topology_attempted_at: float | None = None
        self.topology_observed_at: float | None = None
        self.status_observed_at: float | None = None
        self.topology_failed = False
        self.refreshing = False

    @callback
    def async_register_devices(self) -> None:
        """Update observed devices without tying discovery to enabled entities."""
        if not self.last_update_success:
            return
        registry = dr.async_get(self.hass)
        devices = [device for home in self.data.values() for device in home["devices"]]
        gateways: dict[str, str] = {}
        for device in sorted(devices, key=lambda device: device.type != "NXG"):
            cover = device if isinstance(device, (VeluxWindowData, VeluxShutterData)) else None
            model = (cover.velux_type if cover else None) or device.type
            name = device.name if isinstance(device, VeluxGatewayData) else None
            bridge = None if isinstance(device, VeluxGatewayData) else device.bridge
            registered = registry.async_get_or_create(
                config_entry_id=self._entry.entry_id,
                identifiers={(DOMAIN, device.id)},
                name=name or f"{model.capitalize()} {device.id[-4:]}",
                manufacturer=(cover.manufacturer if cover else None) or "Velux",
                model=model,
                via_device_id=gateways.get(bridge) if bridge is not None else None,
            )
            if device.type == "NXG":
                gateways[device.id] = registered.id

    async def _async_manual_update(self) -> ManualResult:
        """Capture this operation's result before a later poll can change it."""
        await self.async_refresh()
        return self.last_update_success, self.last_exception

    async def async_manual_refresh(self) -> ManualResult:
        """Share entry-owned work; cancellation of a waiter leaves it running."""
        if self._manual_task is None or self._manual_task.done():
            self._manual_task = self._entry.async_create_background_task(
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
                raise HomeAssistantError(
                    "VELUX ACTIVE was unloaded during refresh",
                    translation_domain=DOMAIN,
                    translation_key="unloaded",
                ) from None
            raise

    def _log_device_transitions(self, data: VeluxSnapshot) -> None:
        """Emit one anonymous device transition, regardless of entity count."""
        present = {device.id for home in data.values() for device in home["devices"]}
        for device_id in self._device_reachability.keys() - present:
            if self._device_reachability[device_id] is not False:
                _LOGGER.info("VELUX device %s is unavailable", self._device_log_labels[device_id])
            self._device_reachability[device_id] = False
        for home in data.values():
            for device in home["devices"]:
                reachable = device.reachable is not False
                previous = self._device_reachability.get(device.id)
                self._device_reachability[device.id] = reachable
                label = self._device_log_labels.setdefault(
                    device.id, len(self._device_log_labels) + 1
                )
                if reachable is False and previous is not False:
                    _LOGGER.info("VELUX device %s is unavailable", label)
                elif reachable is True and previous is False:
                    _LOGGER.info("VELUX device %s recovered", label)

    async def _async_update_data(self) -> VeluxSnapshot:
        self.refreshing = True
        try:
            return await self._async_fetch_data()
        finally:
            self.refreshing = False

    async def _async_fetch_data(self) -> VeluxSnapshot:
        try:
            if self.api.auth_token is None:
                await self.api.authenticate(
                    self._entry.data["username"], self._entry.data["password"]
                )
            if (
                self.topology_attempted_at is None
                or monotonic() >= self.topology_attempted_at + 300
            ):
                self.topology_attempted_at = monotonic()
                try:
                    homes = await self.api.get_home_data()
                except InvalidAuthError, RateLimitError:
                    self.topology_failed = True
                    raise
                except APIConnectionError:
                    self.topology_failed = True
                    if self.homes is None:
                        raise
                else:
                    self.homes = homes
                    self.topology_observed_at = monotonic()
                    self.topology_failed = False
            assert self.homes is not None
            data: VeluxSnapshot = {}
            status_ids: set[str] = set()
            for home in self.homes:
                modules = await self.api.get_home_statuses(home)
                home_ids = {module.id for module in modules}
                if status_ids.intersection(home_ids):
                    raise APIConnectionError("VELUX returned ambiguous account status")
                status_ids.update(home_ids)
                data[home] = {
                    "devices": [
                        device
                        for module in modules
                        if (device := device_from_module(module)) is not None
                    ]
                }
            self._log_device_transitions(data)
            self.status_observed_at = monotonic()
            return data
        except InvalidAuthError as err:
            raise ConfigEntryAuthFailed(
                "VELUX login must be renewed",
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        except RateLimitError as err:
            raise UpdateFailed(
                "VELUX cloud requests are temporarily rate limited",
                retry_after=err.retry_after,
                translation_domain=DOMAIN,
                translation_key="rate_limited",
            ) from err
        except APIConnectionError as err:
            raise UpdateFailed(
                "Cannot fetch VELUX cloud data",
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err

    @callback
    def async_can_remove_device(self, device_id: str) -> bool:
        """Authorize manual removal only with fresh, uncontradicted inventory."""
        return (
            not self.refreshing
            and self.last_update_success
            and self.topology_observed_at is not None
            and self.topology_observed_at <= monotonic() < self.topology_observed_at + 300
            and not self.topology_failed
            and device_id not in self.api.inventory_ids
            and device_id not in self.api.status_presence
        )


type VeluxActiveConfigEntry = ConfigEntry[VeluxCoordinator]
