# cover.py

import logging

from homeassistant.components.cover import CoverDeviceClass, CoverEntity
from homeassistant.core import HomeAssistant

from .api import VeluxShutterData, VeluxWindowData
from .coordinator import VeluxActiveConfigEntry
from .entity import VeluxEntity

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0


async def async_setup_entry(hass: HomeAssistant, entry: VeluxActiveConfigEntry, async_add_entities):
    """Set up Velux Active covers from a config entry."""
    coordinator = entry.runtime_data
    covers = []

    for home in coordinator.data:
        devices = coordinator.data[home]["devices"]
        for device in devices:
            if isinstance(device, VeluxWindowData):
                covers.append(VeluxCover(coordinator, device, is_window=True))
            elif isinstance(device, VeluxShutterData):
                covers.append(VeluxCover(coordinator, device, is_window=False))

    async_add_entities(covers)

    return True


class VeluxCover(VeluxEntity, CoverEntity):
    """Representation of a Velux cover (window or shutter)."""

    def __init__(self, coordinator, device, is_window):
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
    def supported_features(self) -> int:
        """Flag supported features."""
        return 0

    @property
    def is_closed(self):
        """Return True if the cover is closed."""
        device = self.device
        if device and device.current_position is not None:
            return device.current_position == 0
        return None

    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        device = self.device
        if device:
            return device.current_position
        return None

    @property
    def extra_state_attributes(self):
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
                "rain_position": getattr(device, "rain_position", None),
                "secure_position": getattr(device, "secure_position", None),
            }
        return {}
