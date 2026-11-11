# cover.py

import logging
from typing import Any

from homeassistant.components.cover import CoverDeviceClass, CoverEntity, CoverEntityFeature
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import (
    APIConnectionError,
    VeluxDevice,
    VeluxGatewayData,
    VeluxShutterData,
    VeluxWindowData,
)
from .coordinator import VeluxActiveConfigEntry, VeluxCoordinator
from .entity import VeluxEntity, async_discover_entities
from .signing import signed_window

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: VeluxActiveConfigEntry, async_add_entities: AddEntitiesCallback
) -> bool:
    """Set up Velux Active covers from a config entry."""

    def create(device: VeluxDevice) -> list[VeluxCover]:
        if isinstance(device, VeluxWindowData):
            return [VeluxCover(entry.runtime_data, device, is_window=True)]
        if isinstance(device, VeluxShutterData):
            return [VeluxCover(entry.runtime_data, device, is_window=False)]
        return []

    async_discover_entities(entry, async_add_entities, create)

    return True


class VeluxCover(VeluxEntity[VeluxWindowData | VeluxShutterData], CoverEntity):
    """Representation of a Velux cover (window or shutter)."""

    def __init__(
        self,
        coordinator: VeluxCoordinator,
        device: VeluxWindowData | VeluxShutterData,
        is_window: bool,
    ) -> None:
        """Initialize the cover."""
        super().__init__(coordinator, device)
        self._is_window = is_window
        self._attr_unique_id = device.id

        # Generate a name using available attributes
        self._attr_name = None

        self._attr_device_class = CoverDeviceClass.WINDOW if is_window else CoverDeviceClass.SHUTTER

    @property
    def supported_features(self) -> CoverEntityFeature:
        """Enable ordinary cover controls only for a paired window."""
        keys = self.coordinator.config_entry.options
        device = self.device
        if (
            isinstance(device, VeluxWindowData)
            and device.bridge == keys.get("gateway_id")
            and all(keys.get(key) for key in ("gateway_id", "hash_sign_key", "sign_key_id"))
        ):
            return (
                CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.SET_POSITION
            )
        return CoverEntityFeature(0)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Request the fully open position."""
        await self.async_set_cover_position(position=100)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Request the closed position."""
        await self.async_set_cover_position(position=0)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Send one signed position command; automation policy belongs to HA."""
        entry = self.coordinator.config_entry
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError("The VELUX cloud account is not loaded")
        if not self.supported_features:
            raise ServiceValidationError("Pair this VELUX gateway before controlling its windows")
        success, _ = await self.coordinator.async_manual_refresh()
        if (
            not success
            or entry.state is not ConfigEntryState.LOADED
            or entry.runtime_data is not self.coordinator
        ):
            raise HomeAssistantError("Cannot verify the current VELUX cloud state")
        keys = dict(entry.options)
        window = self.device
        gateway = next(
            (
                d
                for h in self.coordinator.data.values()
                for d in h["devices"]
                if d.id == keys.get("gateway_id")
            ),
            None,
        )
        if (
            not isinstance(window, VeluxWindowData)
            or window.reachable is not True
            or window.bridge != keys.get("gateway_id")
            or not isinstance(gateway, VeluxGatewayData)
            or window.home.id != gateway.home.id
            or gateway.reachable is False
        ):
            raise ServiceValidationError("A reachable window on the paired gateway is required")
        try:
            await self.coordinator.api.set_state(
                {"id": window.home.id, "modules": [signed_window(window, kwargs["position"], keys)]}
            )
        except (APIConnectionError, ValueError, KeyError) as err:
            raise HomeAssistantError("VELUX window command was not confirmed") from err
        # Commands are never retried or reported as observed positions.
        await self.coordinator.async_request_refresh()

    @property
    def is_closed(self) -> bool | None:
        """Return True if the cover is closed."""
        device = self.device
        if device and device.current_position is not None:
            return device.current_position == 0
        return None

    @property
    def current_cover_position(self) -> int | None:
        """Return the current position of the cover."""
        device = self.device
        if device:
            return device.current_position
        return None

    @property
    def extra_state_attributes(self) -> dict[str, str | int | bool | None]:
        """Return additional state attributes."""
        device = self.device
        if device:
            return {
                "last_seen": device.last_seen,
                "manufacturer": device.manufacturer,
                "reachable": device.reachable,
                "firmware_revision": device.firmware_revision,
                "silent": device.silent,
                "mode": device.mode,
                "velux_type": device.velux_type,
                "bridge": device.bridge,
                "rain_position": device.rain_position
                if isinstance(device, VeluxWindowData)
                else None,
                "secure_position": (
                    device.secure_position if isinstance(device, VeluxWindowData) else None
                ),
            }
        return {}
