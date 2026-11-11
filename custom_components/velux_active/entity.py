"""Common device identity, naming, and coordinator availability."""

from collections.abc import Callable, Sequence

from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import VeluxDevice
from .const import DOMAIN
from .coordinator import VeluxActiveConfigEntry, VeluxCoordinator


class VeluxEntity[DeviceT: VeluxDevice](CoordinatorEntity[VeluxCoordinator]):
    """Reference an existing registry device and the latest snapshot."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: VeluxCoordinator, device: DeviceT) -> None:
        super().__init__(coordinator)
        self._device_id = device.id
        self._device_type: type[DeviceT] = type(device)

    @property
    def device(self) -> DeviceT | None:
        """Return current data, never a cached measurement from an earlier poll."""
        return next(
            (
                device
                for snapshot in self.coordinator.data.values()
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


def async_discover_entities(
    entry: VeluxActiveConfigEntry,
    add_entities: AddEntitiesCallback,
    create: Callable[[VeluxDevice], Sequence[Entity]],
) -> None:
    """Keep one platform listener, including when every entity is disabled."""
    coordinator = entry.runtime_data
    registry = er.async_get(coordinator.hass)
    known: dict[str, Entity] = {}

    @callback
    def discover() -> None:
        if not coordinator.last_update_success:
            return
        for unique_id, entity in tuple(known.items()):
            if entity.entity_id and registry.async_get(entity.entity_id) is None:
                del known[unique_id]
        new: list[Entity] = []
        for home in coordinator.data.values():
            for device in home["devices"]:
                for entity in create(device):
                    candidate_id = entity.unique_id
                    if candidate_id is not None and candidate_id not in known:
                        known[candidate_id] = entity
                        new.append(entity)
        if new:
            add_entities(new)

    discover()
    entry.async_on_unload(coordinator.async_add_listener(discover))
