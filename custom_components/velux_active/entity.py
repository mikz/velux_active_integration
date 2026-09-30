"""Common device identity, naming, and coordinator availability."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import VeluxCoordinator


class VeluxEntity(CoordinatorEntity[VeluxCoordinator]):
    """Reference an existing registry device and the latest snapshot."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: VeluxCoordinator, device):
        super().__init__(coordinator)
        self._device_id = device.id
        self._home = device.home

    @property
    def device(self):
        """Return current data, never a cached measurement from an earlier poll."""
        return next(
            (
                device
                for device in self.coordinator.data.get(self._home, {}).get("devices", [])
                if device.id == self._device_id
            ),
            None,
        )

    @property
    def available(self):
        """Measurements require both a successful poll and a reachable device."""
        device = self.device
        return (
            super().available
            and device is not None
            and getattr(device, "reachable", None) is not False
        )

    @property
    def device_info(self):
        """Reference the device registered before platform setup."""
        return {"identifiers": {(DOMAIN, self._device_id)}}
