# cover.py

import logging

from homeassistant.components.cover import CoverDeviceClass, CoverEntity, CoverEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import VeluxDevice, VeluxShutterData, VeluxWindowData
from .coordinator import VeluxActiveConfigEntry, VeluxCoordinator
from .entity import VeluxEntity, async_discover_entities

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

        # Remove the 'supported_features' attribute as it's deprecated
        # Since the cover is read-only, we don't implement any control methods

    @property
    def supported_features(self) -> CoverEntityFeature:
        """Flag supported features."""
        return CoverEntityFeature(0)

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
