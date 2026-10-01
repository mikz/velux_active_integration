# sensor.py

import logging
from datetime import UTC, datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
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
    """Set up Velux Active sensors from a config entry."""

    def create(device: VeluxDevice) -> list[VeluxSensor]:
        coordinator = entry.runtime_data
        if isinstance(device, VeluxGatewayData):
            return create_gateway_sensors(coordinator, device)
        if isinstance(device, (VeluxWindowData, VeluxShutterData)):
            return create_cover_sensors(coordinator, device)
        if isinstance(device, VeluxSwitchData):
            return create_switch_sensors(coordinator, device)
        return []

    async_discover_entities(entry, async_add_entities, create)

    return True


SENSOR_DESCRIPTIONS = {
    "wifi_strength": SensorEntityDescription(
        key="wifi_strength",
        translation_key="wifi_strength",
        name="Wi-Fi Strength",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "rf_strength": SensorEntityDescription(
        key="rf_strength",
        translation_key="rf_strength",
        name="RF Strength",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "battery_level": SensorEntityDescription(
        key="battery_level",
        translation_key="battery_level",
        name="Battery Level",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "last_seen": SensorEntityDescription(
        key="last_seen",
        translation_key="last_seen",
        name="Last Seen",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "battery_percent": SensorEntityDescription(
        key="battery_percent",
        translation_key="battery_percent",
        name="Battery Percent",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "target_position": SensorEntityDescription(
        key="target_position",
        translation_key="target_position",
        name="Target Position",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "rain_position": SensorEntityDescription(
        key="rain_position",
        translation_key="rain_position",
        name="Rain Position",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


def create_gateway_sensors(
    coordinator: VeluxCoordinator, device: VeluxGatewayData
) -> list[VeluxSensor]:
    """Create sensors for Velux Gateway."""
    return [
        VeluxSensor(coordinator, device, SENSOR_DESCRIPTIONS[key])
        for key in ("wifi_strength", "last_seen")
    ]


def create_cover_sensors(
    coordinator: VeluxCoordinator, device: VeluxWindowData | VeluxShutterData
) -> list[VeluxSensor]:
    """Create sensors for Velux Window or Shutter."""
    keys = ["target_position", "last_seen"]
    if isinstance(device, VeluxWindowData):
        keys.append("rain_position")
    return [VeluxSensor(coordinator, device, SENSOR_DESCRIPTIONS[key]) for key in keys]


def create_switch_sensors(
    coordinator: VeluxCoordinator, device: VeluxSwitchData
) -> list[VeluxSensor]:
    """Create sensors for Velux Switch."""
    return [
        VeluxSensor(coordinator, device, SENSOR_DESCRIPTIONS[key])
        for key in ("battery_level", "battery_percent", "rf_strength", "last_seen")
    ]


class VeluxSensor(VeluxEntity[VeluxDevice], SensorEntity):
    """Representation of a Velux sensor."""

    def __init__(
        self,
        coordinator: VeluxCoordinator,
        device: VeluxDevice,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor without changing legacy unique IDs."""
        super().__init__(coordinator, device)
        self.entity_description = description
        self._attr_unique_id = f"{device.id}_{description.key}"
        self._attribute = description.key

    @property
    def native_value(self) -> str | float | int | datetime | None:
        """Return the value reported by the sensor."""
        device = self.device
        if device:
            value: object = getattr(device, self._attribute, None)
            if self._attribute == "last_seen" and value is not None:
                if isinstance(value, datetime):
                    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    try:
                        return datetime.fromtimestamp(value, UTC)
                    except ValueError, OverflowError, OSError:
                        return None
                return None
            return value if isinstance(value, (str, int, float, datetime)) else None
        return None

    @property
    def extra_state_attributes(self) -> dict[str, str | int | bool | None]:
        """Return additional state attributes."""
        device = self.device
        if device:
            bridge: object = getattr(device, "bridge", None)
            return {
                "last_seen": device.last_seen,
                "reachable": device.reachable,
                "bridge": bridge if isinstance(bridge, str) else None,
            }
        return {}
