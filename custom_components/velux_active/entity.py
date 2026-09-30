"""Common device identity, naming, and coordinator availability."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import VeluxDevice
from .const import DOMAIN
from .coordinator import VeluxCoordinator


class VeluxEntity[DeviceT: VeluxDevice](CoordinatorEntity[VeluxCoordinator]):
    """Reference an existing registry device and the latest snapshot."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: VeluxCoordinator, device: DeviceT) -> None:
        super().__init__(coordinator)
        self._device_id = device.id
        self._home = device.home
        self._device_type: type[DeviceT] = type(device)

    @property
    def device(self) -> DeviceT | None:
        """Return current data, never a cached measurement from an earlier poll."""
        snapshot = self.coordinator.data.get(self._home)
        if snapshot is None:
            return None
        return next(
            (
                device
                for device in snapshot["devices"]
                if device.id == self._device_id and isinstance(device, self._device_type)
            ),
            None,
        )

    @property
    def available(self) -> bool:
        """Measurements require both a successful poll and a reachable device."""
        device = self.device
        return super().available and device is not None and device.reachable is not False

    @property
    def device_info(self) -> DeviceInfo:
        """Reference the device registered before platform setup."""
        return {"identifiers": {(DOMAIN, self._device_id)}}
