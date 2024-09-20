# binary_sensor.py

from datetime import datetime, timezone
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import VeluxGatewayData, VeluxShutterData, VeluxSwitchData, VeluxWindowData
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up Velux Active binary sensors from a config entry."""
    coordinator = hass.data[DOMAIN]["coordinator"]
    binary_sensors = []

    for home in hass.data[DOMAIN]["homes"]:
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

def create_gateway_binary_sensors(coordinator, device):
    """Create binary sensors for Velux Gateway."""
    sensors = []
    device_name = f"Gateway {device.name}"
    # Sensor for is_raining
    sensors.append(VeluxBinarySensor(
        coordinator,
        device,
        name=f"{device_name} Is Raining",
        attribute="is_raining",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ))
    # Sensor for locked
    sensors.append(VeluxBinarySensor(
        coordinator,
        device,
        name=f"{device_name} Locked",
        attribute="unlocked",
        device_class=BinarySensorDeviceClass.LOCK,
    ))
    # Sensor for locking
    sensors.append(VeluxBinarySensor(
        coordinator,
        device,
        name=f"{device_name} Locking",
        attribute="locking",
        device_class=BinarySensorDeviceClass.MOVING,
    ))
    # Sensor for calibrating
    sensors.append(VeluxBinarySensor(
        coordinator,
        device,
        name=f"{device_name} Calibrating",
        attribute="calibrating",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ))
    # Sensor for busy
    sensors.append(VeluxBinarySensor(
        coordinator,
        device,
        name=f"{device_name} Busy",
        attribute="busy",
        device_class=BinarySensorDeviceClass.RUNNING,
    ))
    return sensors

def create_cover_binary_sensors(coordinator, device):
    """Create binary sensors for Velux Window or Shutter."""
    sensors = []
    device_name = f"{device.velux_type.capitalize()} {device.id[-4:]}"
    # Sensor for reachable
    sensors.append(VeluxBinarySensor(
        coordinator,
        device,
        name=f"{device_name} Reachable",
        attribute="reachable",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ))
    # Sensor for silent
    sensors.append(VeluxBinarySensor(
        coordinator,
        device,
        name=f"{device_name} Silent Mode",
        attribute="silent",
        device_class=BinarySensorDeviceClass.RUNNING,
    ))
    return sensors

def create_switch_binary_sensors(coordinator, device):
    """Create binary sensors for Velux Switch."""
    sensors = []
    device_name = f"Switch {device.id[-4:]}"
    # Sensor for reachable
    sensors.append(VeluxBinarySensor(
        coordinator,
        device,
        name=f"{device_name} Reachable",
        attribute="reachable",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ))
    return sensors

class VeluxBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Velux binary sensor."""

    def __init__(
        self,
        coordinator,
        device,
        name,
        attribute,
        device_class=None,
    ):
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._device_id = device.id
        self._home = device.home
        self._attr_unique_id = f"{device.id}_{attribute}"
        self._attr_name = name
        self._attribute = attribute
        self._attr_device_class = device_class

    @property
    def device(self):
        """Return the current device object from the coordinator data."""
        devices = self.coordinator.data.get(self._home, {}).get("devices", [])
        for dev in devices:
            if dev.id == self._device_id:
                return dev
        return None

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        device = self.device
        if device:
            value = getattr(device, self._attribute, None)
            return bool(value) if value is not None else None
        return None

    @property
    def extra_state_attributes(self):
        """Return additional state attributes."""
        device = self.device
        if device:
            return {
                "last_seen": device.last_seen
            }
        return {}

    @property
    def device_info(self):
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

    @property
    def available(self):
        """Return True if entity is available."""
        device = self.device
        return device is not None and getattr(device, "reachable", True)