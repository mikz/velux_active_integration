# sensor.py

from datetime import datetime, timezone
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfElectricPotential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import VeluxGatewayData, VeluxShutterData, VeluxSwitchData, VeluxWindowData
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up Velux Active sensors from a config entry."""
    coordinator = hass.data[DOMAIN]["coordinator"]
    sensors = []

    for home in hass.data[DOMAIN]["homes"]:
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
    device_name = f"Gateway {device.name}"
    # Sensor for wifi_strength
    sensors.append(VeluxSensor(
        coordinator,
        device,
        name=f"{device_name} Wi-Fi Strength",
        attribute="wifi_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement="dBm",
        state_class=SensorStateClass.MEASUREMENT,
    ))

    sensors.append(VeluxSensor(
        coordinator,
        device,
        name=f"{device_name} Last Seen",
        attribute="last_seen",
        device_class=SensorDeviceClass.TIMESTAMP,
    ))
    
    return sensors

def create_cover_sensors(coordinator, device):
    """Create sensors for Velux Window or Shutter."""
    sensors = []
    device_name = f"{device.velux_type.capitalize()} {device.id[-4:]}"
    # Sensor for target_position
    sensors.append(VeluxSensor(
        coordinator,
        device,
        name=f"{device_name} Target Position",
        attribute="target_position",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ))
    # Sensor for rain_position (windows only)
    if hasattr(device, 'rain_position'):
        sensors.append(VeluxSensor(
            coordinator,
            device,
            name=f"{device_name} Rain Position",
            attribute="rain_position",
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
        ))

    sensors.append(VeluxSensor(
        coordinator,
        device,
        name=f"{device_name} Last Seen",
        attribute="last_seen",
        device_class=SensorDeviceClass.TIMESTAMP,
    ))
    return sensors

def create_switch_sensors(coordinator, device):
    """Create sensors for Velux Switch."""
    sensors = []
    device_name = f"Switch {device.id[-4:]}"
    # Sensor for battery_level
    sensors.append(VeluxSensor(
        coordinator,
        device,
        name=f"{device_name} Battery Level",
        attribute="battery_level",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ))
    # Sensor for battery_percent
    if hasattr(device, 'battery_percent'):
        sensors.append(VeluxSensor(
            coordinator,
            device,
            name=f"{device_name} Battery Percent",
            attribute="battery_percent",
            device_class=SensorDeviceClass.BATTERY,
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
        ))
    # Sensor for rf_strength
    sensors.append(VeluxSensor(
        coordinator,
        device,
        name=f"{device_name} RF Strength",
        attribute="rf_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement="dBm",
        state_class=SensorStateClass.MEASUREMENT,
    ))

    sensors.append(VeluxSensor(
        coordinator,
        device,
        name=f"{device_name} Last Seen",
        attribute="last_seen",
        device_class=SensorDeviceClass.TIMESTAMP,
    ))

    return sensors

class VeluxSensor(CoordinatorEntity, SensorEntity):
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
        super().__init__(coordinator)
        self._device_id = device.id
        self._home = device.home
        self._attr_unique_id = f"{device.id}_{attribute}"
        self._attr_name = name
        self._attribute = attribute
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = native_unit_of_measurement
        self._attr_state_class = state_class

    @property
    def device(self):
        """Return the current device object from the coordinator data."""
        devices = self.coordinator.data.get(self._home, {}).get("devices", [])
        for dev in devices:
            if dev.id == self._device_id:
                return dev
        return None

    @property
    def native_value(self):
        """Return the value reported by the sensor."""
        device = self.device
        if device:
            value = getattr(device, self._attribute, None)
            if self._attribute == 'last_seen' and value is not None:
                # Convert the integer timestamp to a timezone-aware datetime object
                return datetime.fromtimestamp(value, timezone.utc)
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

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        device = self.device
        if device:
            # Determine the device type
            device_type = getattr(device, 'type', device.type).lower()
            # Check if the device is a Gateway
            if device_type == 'nxg':
                # For Gateway devices
                device_name = device.name or 'Gateway'
                manufacturer = getattr(device, 'manufacturer', 'Velux')
                model = 'Gateway'
                via_device = None  # Gateway is the root device
            else:
                # For other devices
                manufacturer = getattr(device, 'manufacturer', 'Velux')
                model = getattr(device, 'velux_type', device.type)
                device_name = f"{model.capitalize()} {device.id[-4:]}"
                # Reference the Gateway as the via_device
                via_device = (DOMAIN, getattr(device, 'bridge', None))
            device_info = {
                "identifiers": {(DOMAIN, self._device_id)},
                "name": device_name,
                "manufacturer": manufacturer,
                "model": model,
                "sw_version": getattr(device, "firmware_revision", None),
            }
            if via_device:
                device_info["via_device"] = via_device
            return device_info
        return None