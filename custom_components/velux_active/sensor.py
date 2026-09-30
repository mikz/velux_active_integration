# sensor.py

import logging
from datetime import UTC, datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfElectricPotential
from homeassistant.core import HomeAssistant

from .api import VeluxGatewayData, VeluxShutterData, VeluxSwitchData, VeluxWindowData
from .coordinator import VeluxActiveConfigEntry
from .entity import VeluxEntity

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0


async def async_setup_entry(hass: HomeAssistant, entry: VeluxActiveConfigEntry, async_add_entities):
    """Set up Velux Active sensors from a config entry."""
    coordinator = entry.runtime_data
    sensors = []

    for home in coordinator.data:
        devices = coordinator.data[home]["devices"]
        for device in devices:
            if isinstance(device, VeluxGatewayData):
                sensors.extend(create_gateway_sensors(coordinator, device))
            elif isinstance(device, (VeluxWindowData, VeluxShutterData)):
                sensors.extend(create_cover_sensors(coordinator, device))
            elif isinstance(device, VeluxSwitchData):
                sensors.extend(create_switch_sensors(coordinator, device))

    async_add_entities(sensors)

    return True


def create_gateway_sensors(coordinator, device):
    """Create sensors for Velux Gateway."""
    sensors = []
    # Sensor for wifi_strength
    sensors.append(
        VeluxSensor(
            coordinator,
            device,
            name="Wi-Fi Strength",
            attribute="wifi_strength",
            device_class=SensorDeviceClass.SIGNAL_STRENGTH,
            native_unit_of_measurement="dBm",
            state_class=SensorStateClass.MEASUREMENT,
        )
    )

    sensors.append(
        VeluxSensor(
            coordinator,
            device,
            name="Last Seen",
            attribute="last_seen",
            device_class=SensorDeviceClass.TIMESTAMP,
        )
    )

    return sensors


def create_cover_sensors(coordinator, device):
    """Create sensors for Velux Window or Shutter."""
    sensors = []
    # Sensor for target_position
    sensors.append(
        VeluxSensor(
            coordinator,
            device,
            name="Target Position",
            attribute="target_position",
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
        )
    )
    # Sensor for rain_position (windows only)
    if hasattr(device, "rain_position"):
        sensors.append(
            VeluxSensor(
                coordinator,
                device,
                name="Rain Position",
                attribute="rain_position",
                native_unit_of_measurement=PERCENTAGE,
                state_class=SensorStateClass.MEASUREMENT,
            )
        )

    sensors.append(
        VeluxSensor(
            coordinator,
            device,
            name="Last Seen",
            attribute="last_seen",
            device_class=SensorDeviceClass.TIMESTAMP,
        )
    )
    return sensors


def create_switch_sensors(coordinator, device):
    """Create sensors for Velux Switch."""
    sensors = []
    # Sensor for battery_level
    sensors.append(
        VeluxSensor(
            coordinator,
            device,
            name="Battery Level",
            attribute="battery_level",
            device_class=SensorDeviceClass.VOLTAGE,
            native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
            state_class=SensorStateClass.MEASUREMENT,
        )
    )
    # Sensor for battery_percent
    if hasattr(device, "battery_percent"):
        sensors.append(
            VeluxSensor(
                coordinator,
                device,
                name="Battery Percent",
                attribute="battery_percent",
                device_class=SensorDeviceClass.BATTERY,
                native_unit_of_measurement=PERCENTAGE,
                state_class=SensorStateClass.MEASUREMENT,
            )
        )
    # Sensor for rf_strength
    sensors.append(
        VeluxSensor(
            coordinator,
            device,
            name="RF Strength",
            attribute="rf_strength",
            device_class=SensorDeviceClass.SIGNAL_STRENGTH,
            native_unit_of_measurement="dBm",
            state_class=SensorStateClass.MEASUREMENT,
        )
    )

    sensors.append(
        VeluxSensor(
            coordinator,
            device,
            name="Last Seen",
            attribute="last_seen",
            device_class=SensorDeviceClass.TIMESTAMP,
        )
    )

    return sensors


class VeluxSensor(VeluxEntity, SensorEntity):
    """Representation of a Velux sensor."""

    def __init__(
        self,
        coordinator,
        device,
        name,
        attribute,
        device_class=None,
        native_unit_of_measurement=None,
        state_class=None,
    ):
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.id}_{attribute}"
        self._attr_name = name
        self._attribute = attribute
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = native_unit_of_measurement
        self._attr_state_class = state_class

    @property
    def native_value(self):
        """Return the value reported by the sensor."""
        device = self.device
        if device:
            value = getattr(device, self._attribute, None)
            if self._attribute == "last_seen" and value is not None:
                if isinstance(value, datetime):
                    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    try:
                        return datetime.fromtimestamp(value, UTC)
                    except ValueError, OverflowError, OSError:
                        return None
                return None
            return value
        return None

    @property
    def extra_state_attributes(self):
        """Return additional state attributes."""
        device = self.device
        if device:
            return {
                "last_seen": device.last_seen,
                "reachable": getattr(device, "reachable", None),
                "bridge": getattr(device, "bridge", None),
            }
        return {}
