"""Reproduce failures in the original integration without production access."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

from custom_components.velux_active import async_unload_entry
from custom_components.velux_active.api import AuthToken, VeluxActiveAPI
from custom_components.velux_active.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
    VeluxBinarySensor,
)


async def test_three_hour_token_is_not_refreshed_after_one_minute():
    api = VeluxActiveAPI(AsyncMock())
    api.auth_token = AuthToken("synthetic-access", "synthetic-refresh", 10800)
    api.auth_token.expires_at = datetime.now() + timedelta(hours=2)
    api.refresh_access_token = AsyncMock()
    assert await api.access_token == "synthetic-access"
    api.refresh_access_token.assert_not_called()


async def test_unload_does_not_read_credentials_as_runtime_data():
    hass = SimpleNamespace(
        data={"velux_active": {}},
        config_entries=SimpleNamespace(async_unload_platforms=AsyncMock(return_value=True)),
        services=SimpleNamespace(async_remove=lambda *args: None),
    )
    entry = SimpleNamespace(data={"username": "lab@example.invalid", "password": "lab-only"})
    assert await async_unload_entry(hass, entry)


def test_rain_sensor_becomes_unavailable_when_poll_fails():
    home = "synthetic-home"
    device = SimpleNamespace(id="gateway", home=home, is_raining=False)
    coordinator = SimpleNamespace(data={home: {"devices": [device]}}, last_update_success=False)
    entity = VeluxBinarySensor(coordinator, device, BINARY_SENSOR_DESCRIPTIONS["is_raining"])
    assert entity.available is False
