# binary_sensor.py

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import VeluxDevice, VeluxGatewayData, VeluxShutterData, VeluxSwitchData, VeluxWindowData
from .coordinator import VeluxActiveConfigEntry, VeluxCoordinator
from .entity import VeluxEntity

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: VeluxActiveConfigEntry, async_add_entities: AddEntitiesCallback
) -> bool:
    """Set up Velux Active binary sensors from a config entry."""
    coordinator = entry.runtime_data
    binary_sensors = []

    for home in coordinator.data:
        devices = coordinator.data[home]["devices"]
        for device in devices:
            if isinstance(device, VeluxGatewayData):
                binary_sensors.extend(create_gateway_binary_sensors(coordinator, device))
            elif isinstance(device, (VeluxWindowData, VeluxShutterData)):
                binary_sensors.extend(create_cover_binary_sensors(coordinator, device))
            elif isinstance(device, VeluxSwitchData):
                binary_sensors.extend(create_switch_binary_sensors(coordinator, device))

    async_add_entities(binary_sensors)

    return True


def create_gateway_binary_sensors(
    coordinator: VeluxCoordinator, device: VeluxGatewayData
) -> list[VeluxBinarySensor]:
    """Create binary sensors for Velux Gateway."""
    sensors = []
    # Sensor for is_raining
    sensors.append(
        VeluxBinarySensor(
            coordinator,
            device,
            name="Is Raining",
            attribute="is_raining",
            device_class=BinarySensorDeviceClass.MOISTURE,
        )
    )
    # Sensor for locked
    sensors.append(
        VeluxBinarySensor(
            coordinator,
            device,
            name="Locked",
            attribute="unlocked",
            device_class=BinarySensorDeviceClass.LOCK,
        )
    )
    # Sensor for locking
    sensors.append(
        VeluxBinarySensor(
            coordinator,
            device,
            name="Locking",
            attribute="locking",
            device_class=BinarySensorDeviceClass.MOVING,
        )
    )
    # Sensor for calibrating
    sensors.append(
        VeluxBinarySensor(
            coordinator,
            device,
            name="Calibrating",
            attribute="calibrating",
            device_class=BinarySensorDeviceClass.PROBLEM,
        )
    )
    # Sensor for busy
    sensors.append(
        VeluxBinarySensor(
            coordinator,
            device,
            name="Busy",
            attribute="busy",
            device_class=BinarySensorDeviceClass.RUNNING,
        )
    )
    return sensors


def create_cover_binary_sensors(
    coordinator: VeluxCoordinator, device: VeluxWindowData | VeluxShutterData
) -> list[VeluxBinarySensor]:
    """Create binary sensors for Velux Window or Shutter."""
    sensors = []
    # Sensor for reachable
    sensors.append(
        VeluxBinarySensor(
            coordinator,
            device,
            name="Reachable",
            attribute="reachable",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
        )
    )
    # Sensor for silent
    sensors.append(
        VeluxBinarySensor(
            coordinator,
            device,
            name="Silent Mode",
            attribute="silent",
            device_class=BinarySensorDeviceClass.RUNNING,
        )
    )
    return sensors


def create_switch_binary_sensors(
    coordinator: VeluxCoordinator, device: VeluxSwitchData
) -> list[VeluxBinarySensor]:
    """Create binary sensors for Velux Switch."""
    sensors = []
    # Sensor for reachable
    sensors.append(
        VeluxBinarySensor(
            coordinator,
            device,
            name="Reachable",
            attribute="reachable",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
        )
    )
    return sensors


class VeluxBinarySensor(VeluxEntity[VeluxDevice], BinarySensorEntity):
    """Representation of a Velux binary sensor."""

    def __init__(
        self,
        coordinator: VeluxCoordinator,
        device: VeluxDevice,
        name: str,
        attribute: str,
        device_class: BinarySensorDeviceClass | None = None,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.id}_{attribute}"
        self._attr_name = name
        self._attribute = attribute
        self._attr_device_class = device_class

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
