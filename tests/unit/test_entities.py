"""Sparse and disconnected device snapshots preserve unknown and valid zero values."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from custom_components.velux_active.api import VeluxGatewayData, VeluxHome, VeluxWindowData
from custom_components.velux_active.binary_sensor import VeluxBinarySensor
from custom_components.velux_active.cover import VeluxCover
from custom_components.velux_active.sensor import VeluxSensor


@pytest.fixture
def snapshot():
    home = VeluxHome("synthetic-home", "Synthetic")
    device = VeluxWindowData(
        home=home,
        id="synthetic-window",
        type="NXO",
        velux_type="window",
        reachable=True,
        current_position=0,
    )
    coordinator = SimpleNamespace(data={home: {"devices": [device]}}, last_update_success=True)
    return coordinator, device


def test_missing_devices_and_measurements_never_retain_previous_snapshot(snapshot):
    coordinator, device = snapshot
    cover = VeluxCover(coordinator, device, True)
    sensor = VeluxSensor(coordinator, device, "Target position", "target_position")
    binary = VeluxBinarySensor(coordinator, device, "Connectivity", "reachable")
    assert cover.is_closed is True and cover.current_cover_position == 0
    assert sensor.native_value is None
    assert binary.is_on is True
    assert cover.has_entity_name and cover.name is None
    assert sensor.extra_state_attributes["reachable"] is True
    assert binary.extra_state_attributes == {"last_seen": None}
    coordinator.data = {}
    for entity in (cover, sensor, binary):
        assert not entity.available
        assert entity.extra_state_attributes == {}
    assert cover.is_closed is None and cover.current_cover_position is None
    assert sensor.native_value is None and binary.is_on is None


def test_unreachable_connectivity_is_available_but_measurements_are_unavailable(snapshot):
    coordinator, device = snapshot
    device.reachable = False
    connectivity = VeluxBinarySensor(coordinator, device, "Connectivity", "reachable")
    cover = VeluxCover(coordinator, device, True)
    sensor = VeluxSensor(coordinator, device, "Target", "target_position")
    assert connectivity.available and connectivity.is_on is False
    assert not cover.available and not sensor.available
    device.reachable = True
    assert connectivity.available and cover.available and sensor.available
    coordinator.last_update_success = False
    assert not connectivity.available and not cover.available and not sensor.available


@pytest.mark.parametrize(
    "value,expected",
    [
        (0, datetime.fromtimestamp(0, UTC)),
        (1.5, datetime.fromtimestamp(1.5, UTC)),
        (datetime(2026, 1, 1), datetime(2026, 1, 1, tzinfo=UTC)),
        (datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 1, tzinfo=UTC)),
        (None, None),
        (False, None),
        ("invalid", None),
        (10**100, None),
    ],
)
def test_timestamps_are_typed_aware_or_unknown(snapshot, value, expected):
    coordinator, device = snapshot
    device.last_seen = value
    assert VeluxSensor(coordinator, device, "Last seen", "last_seen").native_value == expected


def test_zero_position_and_false_measurements_are_valid(snapshot):
    coordinator, device = snapshot
    device.current_position = None
    assert VeluxCover(coordinator, device, True).is_closed is None
    device.target_position = 0
    assert VeluxSensor(coordinator, device, "Target", "target_position").native_value == 0
    device.silent = False
    assert VeluxBinarySensor(coordinator, device, "Silent", "silent").is_on is False
    device.silent = None
    assert VeluxBinarySensor(coordinator, device, "Silent", "silent").is_on is None
    gateway = VeluxGatewayData(home=device.home, id="gateway", type="NXG")
    coordinator.data[device.home]["devices"] = [gateway]
    assert gateway.unlocked is None
    rain = VeluxBinarySensor(coordinator, gateway, "Rain", "is_raining")
    assert rain.available and rain.is_on is None
