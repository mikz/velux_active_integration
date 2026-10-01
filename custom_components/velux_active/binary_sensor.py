# binary_sensor.py

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import VeluxDevice, VeluxGatewayData, VeluxShutterData, VeluxSwitchData, VeluxWindowData
from .coordinator import VeluxActiveConfigEntry, VeluxCoordinator
from .entity import VeluxEntity, async_discover_entities

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: VeluxActiveConfigEntry, async_add_entities: AddEntitiesCallback
) -> bool:
    """Set up Velux Active binary sensors from a config entry."""

    def create(device: VeluxDevice) -> list[VeluxBinarySensor]:
        coordinator = entry.runtime_data
        if isinstance(device, VeluxGatewayData):
            return create_gateway_binary_sensors(coordinator, device)
        if isinstance(device, (VeluxWindowData, VeluxShutterData)):
            return create_cover_binary_sensors(coordinator, device)
        if isinstance(device, VeluxSwitchData):
            return create_switch_binary_sensors(coordinator, device)
        return []

    async_discover_entities(entry, async_add_entities, create)

    return True


BINARY_SENSOR_DESCRIPTIONS = {
    "is_raining": BinarySensorEntityDescription(
        key="is_raining",
        translation_key="is_raining",
        name="Is Raining",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    "unlocked": BinarySensorEntityDescription(
        key="unlocked",
        translation_key="unlocked",
        name="Locked",
        device_class=BinarySensorDeviceClass.LOCK,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "locking": BinarySensorEntityDescription(
        key="locking",
        translation_key="locking",
        name="Locking",
        device_class=BinarySensorDeviceClass.MOVING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "calibrating": BinarySensorEntityDescription(
        key="calibrating",
        translation_key="calibrating",
        name="Calibrating",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "busy": BinarySensorEntityDescription(
        key="busy",
        translation_key="busy",
        name="Busy",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "reachable": BinarySensorEntityDescription(
        key="reachable",
        translation_key="reachable",
        name="Reachable",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "silent": BinarySensorEntityDescription(
        key="silent",
        translation_key="silent",
        name="Silent Mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
}


def create_gateway_binary_sensors(
    coordinator: VeluxCoordinator, device: VeluxGatewayData
) -> list[VeluxBinarySensor]:
    """Create sensors for Velux Gateway."""
    return [
        VeluxBinarySensor(coordinator, device, BINARY_SENSOR_DESCRIPTIONS[key])
        for key in ("is_raining", "unlocked", "locking", "calibrating", "busy")
    ]


def create_cover_binary_sensors(
    coordinator: VeluxCoordinator, device: VeluxWindowData | VeluxShutterData
) -> list[VeluxBinarySensor]:
    """Create sensors for Velux Window or Shutter."""
    return [
        VeluxBinarySensor(coordinator, device, BINARY_SENSOR_DESCRIPTIONS[key])
        for key in ("reachable", "silent")
    ]


def create_switch_binary_sensors(
    coordinator: VeluxCoordinator, device: VeluxSwitchData
) -> list[VeluxBinarySensor]:
    """Create sensors for Velux Switch."""
    return [VeluxBinarySensor(coordinator, device, BINARY_SENSOR_DESCRIPTIONS["reachable"])]


class VeluxBinarySensor(VeluxEntity[VeluxDevice], BinarySensorEntity):
    """Representation of a Velux binary sensor."""

    def __init__(
        self,
        coordinator: VeluxCoordinator,
        device: VeluxDevice,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor without changing legacy unique IDs."""
        super().__init__(coordinator, device)
        self.entity_description = description
        self._attr_unique_id = f"{device.id}_{description.key}"
        self._attribute = description.key

    @property
    def is_on(self) -> bool | None:
        """Return True if the binary sensor is on."""
        device = self.device
        if device:
            value: object = getattr(device, self._attribute, None)
            return value if isinstance(value, bool) else None
        return None

    @property
    def extra_state_attributes(self) -> dict[str, int | None]:
        """Return additional state attributes."""
        device = self.device
        if device:
            return {"last_seen": device.last_seen}
        return {}

    @property
    def available(self) -> bool:
        """Connectivity stays available to report a disconnected device."""
        if self._attribute == "reachable":
            return self.coordinator.last_update_success and self.device is not None
        return super().available
