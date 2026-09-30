# cover.py

import logging

from homeassistant.components.cover import CoverDeviceClass, CoverEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import VeluxShutterData, VeluxWindowData
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
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
            else:
                _LOGGER.debug("Device is not a window or shutter: %s", device)

    async_add_entities(covers)

    return True


class VeluxCover(CoordinatorEntity, CoverEntity):
    """Representation of a Velux cover (window or shutter)."""

    def __init__(self, coordinator, device, is_window):
        """Initialize the cover."""
        super().__init__(coordinator)
        self._device_id = device.id
        self._home = device.home
        self._is_window = is_window
        self._attr_unique_id = device.id

        # Generate a name using available attributes
        self._attr_name = f"{device.velux_type.capitalize()} {device.id[-4:]}"

        self._attr_device_class = CoverDeviceClass.WINDOW if is_window else CoverDeviceClass.SHUTTER

        # Remove the 'supported_features' attribute as it's deprecated
        # Since the cover is read-only, we don't implement any control methods

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return 0

    @property
    def device(self):
        """Return the current device object from the coordinator data."""
        devices = self.coordinator.data.get(self._home, {}).get("devices", [])
        for dev in devices:
            if dev.id == self._device_id:
                return dev
        return None

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

    @property
    def available(self):
        """Return True if entity is available."""
        device = self.device
        return super().available and device is not None and device.reachable is not False

    @property
    def device_info(self):
        """Reference the device registered before platform setup."""
        return {"identifiers": {(DOMAIN, self._device_id)}}
