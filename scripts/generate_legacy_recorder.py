"""Prepare a synthetic pre-candidate SQLite recorder via the pinned native HA fixture.

Run: uv run pytest scripts/generate_legacy_recorder.py -q
"""

import sqlite3
from datetime import timedelta
from pathlib import Path

import pytest
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder.statistics import async_import_statistics
from homeassistant.util import dt as dt_util
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def mock_recorder_before_hass(recorder_db_url):
    """Prepare the native database before constructing HA."""


@pytest.mark.parametrize("persistent_database", [True])
async def test_generate_synthetic_recorder(recorder_mock, hass, persistent_database):
    previous = (dt_util.utcnow() - timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    for identifier, raw, unit in (
        ("sensor.synthetic_legacy_lab_gateway_wifi_strength", 44, "dBm"),
        ("sensor.synthetic_legacy_lab_switch_rf_strength", 64, "dBm"),
        ("sensor.synthetic_legacy_lab_switch_battery_level", 3724, "mV"),
    ):
        async_import_statistics(
            hass,
            {
                "statistic_id": identifier,
                "source": "recorder",
                "name": None,
                "mean_type": StatisticMeanType.ARITHMETIC,
                "has_sum": False,
                "unit_class": "voltage" if unit == "mV" else None,
                "unit_of_measurement": unit,
            },
            [{"start": previous, "mean": raw, "min": raw, "max": raw}],
        )
    await recorder_mock.async_block_till_done()
    source = make_url(recorder_mock.db_url).database
    destination = ROOT / ".lab/legacy-recorder.db"

    def export():
        destination.parent.mkdir(exist_ok=True)
        destination.unlink(missing_ok=True)
        with sqlite3.connect(source) as original, sqlite3.connect(destination) as target:
            original.backup(target)
            assert target.execute("SELECT count(*) FROM statistics").fetchone()[0] == 3

    await hass.async_add_executor_job(export)
