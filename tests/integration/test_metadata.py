"""Native metadata, localization and historical statistics compatibility."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder.statistics import (
    async_import_statistics,
    get_metadata,
    statistics_during_period,
    update_statistics_issues,
)
from homeassistant.components.recorder.tasks import StatisticsTask, SynchronizeTask
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.translation import async_get_translations
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.velux_active.const import DOMAIN
from tests.integration.test_quality import loaded as loaded
from tests.integration.test_quality import refresh
from tests.lab.cloud import PASSWORD, USERNAME


@pytest.fixture
def mock_recorder_before_hass(recorder_db_url):
    """Prepare the native recorder database before the HA fixture starts."""


async def test_new_diagnostic_defaults_and_useful_measurements(hass, loaded):
    entry, _, _ = loaded
    registry = er.async_get(hass)
    records = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert len(records) == 23
    for record in records:
        secondary = record.unique_id.endswith(
            (
                "_wifi_strength",
                "_rf_strength",
                "_battery_level",
                "_last_seen",
                "_unlocked",
                "_locking",
                "_calibrating",
                "_busy",
                "_silent",
            )
        )
        assert record.disabled_by == (er.RegistryEntryDisabler.INTEGRATION if secondary else None)
        if secondary or record.unique_id.endswith("_reachable"):
            assert record.entity_category.value == "diagnostic"
    battery = registry.async_get_entity_id("sensor", DOMAIN, "lab-switch_battery_percent")
    assert hass.states.get(battery).attributes["unit_of_measurement"] == "%"
    assert hass.states.get(battery).attributes["device_class"] == "battery"
    cover = registry.async_get_entity_id("cover", DOMAIN, "lab-window")
    assert registry.async_get(cover).original_name is None
    assert hass.states.get(cover).state == "open"


@pytest.mark.parametrize(
    "language,expected", [("en", "Is Raining"), ("cs", "Déšť"), ("de", "Is Raining")]
)
async def test_native_entity_and_exception_translation_with_fallback(hass, language, expected):
    entities = await async_get_translations(hass, language, "entity", {DOMAIN})
    assert entities[f"component.{DOMAIN}.entity.binary_sensor.is_raining.name"] == expected
    errors = await async_get_translations(hass, language, "exceptions", {DOMAIN})
    assert errors[f"component.{DOMAIN}.exceptions.refresh_failed.message"] == (
        "Aktualizace cloudu VELUX ACTIVE selhala"
        if language == "cs"
        else "VELUX ACTIVE cloud refresh failed"
    )


async def test_legacy_raw_diagnostics_keep_ids_options_and_historical_statistics(
    recorder_mock, hass, cloud
):
    simulator, api = cloud
    entry = MockConfigEntry(
        domain=DOMAIN, version=1, data={"username": USERNAME, "password": PASSWORD}
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    old = {}
    previous = datetime(2026, 1, 1, tzinfo=UTC)
    for device_id, attribute, raw, unit in (
        ("lab-gateway", "wifi_strength", 44, "dBm"),
        ("lab-switch", "rf_strength", 64, "dBm"),
        ("lab-switch", "battery_level", 3724, "mV"),
    ):
        record = registry.async_get_or_create(
            "sensor",
            DOMAIN,
            f"{device_id}_{attribute}",
            config_entry=entry,
            suggested_object_id=f"legacy_{attribute}",
            original_name=f"Original {attribute}",
        )
        options = {"sensor": {"display_precision": 2}}
        if attribute == "battery_level":
            options["sensor"]["unit_of_measurement"] = "V"
        registry.async_update_entity(record.entity_id, name=f"My {attribute}")
        record = registry.async_update_entity_options(record.entity_id, "sensor", options["sensor"])
        old[attribute] = record
        hass.states.async_set(
            record.entity_id,
            raw,
            {
                "state_class": "measurement",
                "unit_of_measurement": unit,
                "device_class": "voltage" if unit == "mV" else "signal_strength",
            },
        )
        async_import_statistics(
            hass,
            {
                "statistic_id": record.entity_id,
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
    before = await hass.async_add_executor_job(get_metadata, hass)
    # The previous integration unloads its live states before candidate setup.
    for record in old.values():
        hass.states.async_remove(record.entity_id)
    await hass.async_block_till_done()
    simulator.state["status_payload"] = {
        "body": {
            "home": {
                "modules": [
                    {"id": "lab-gateway", "wifi_strength": 44, "reachable": True},
                    {
                        "id": "lab-switch",
                        "rf_strength": 64,
                        "battery_level": 3724,
                        "battery_percent": 82,
                        "reachable": True,
                    },
                ]
            }
        }
    }
    with patch("custom_components.velux_active.coordinator.VeluxActiveAPI", return_value=api):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await refresh(hass)
        for attribute, raw in (("wifi_strength", 44), ("rf_strength", 64), ("battery_level", 3724)):
            record = old[attribute]
            current = registry.async_get(record.entity_id)
            assert current.id == record.id and current.unique_id == record.unique_id
            assert current.name == record.name and current.options == record.options
            assert current.disabled_by is None
            state = hass.states.get(record.entity_id)
            assert float(state.state) == raw
            assert "unit_of_measurement" not in state.attributes
            assert "state_class" not in state.attributes and "device_class" not in state.attributes
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
    await recorder_mock.async_block_till_done()
    now = dt_util.utcnow()
    current_period = now.replace(minute=now.minute // 5 * 5, second=0, microsecond=0)
    committed = hass.loop.create_future()
    recorder_mock.queue_task(StatisticsTask(current_period, False))
    recorder_mock.queue_task(SynchronizeTask(committed))
    await committed
    after = await hass.async_add_executor_job(get_metadata, hass)
    assert before == {key: after[key] for key in before}
    history = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        previous,
        previous + timedelta(days=1),
        {record.entity_id for record in old.values()},
        "hour",
        None,
        {"mean", "min", "max"},
    )
    for attribute, raw in (("wifi_strength", 44), ("rf_strength", 64), ("battery_level", 3724)):
        assert len(history[old[attribute].entity_id]) == 1
        assert history[old[attribute].entity_id][0]["mean"] == raw
    future = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        current_period,
        None,
        {record.entity_id for record in old.values()},
        "5minute",
        None,
        {"mean"},
    )
    assert not future  # Native compilation creates no unitless or converted replacements.
    battery_percent = registry.async_get_entity_id("sensor", DOMAIN, "lab-switch_battery_percent")
    positive = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        current_period,
        None,
        {battery_percent},
        "5minute",
        None,
        {"mean"},
    )
    assert len(positive[battery_percent]) == 1
    assert positive[battery_percent][0]["mean"] == pytest.approx(82)
    await recorder_mock.async_add_executor_job(update_statistics_issues, hass)
    await hass.async_block_till_done()
    expected_issues = {
        ("sensor", f"{kind}_{record.entity_id}")
        for record in old.values()
        for kind in ("state_class_removed", "units_changed")
    }
    assert set(ir.async_get(hass).issues) == expected_issues
    assert all(battery_percent not in issue_id for _, issue_id in expected_issues)


async def test_fresh_statistics_validation_has_no_history_warnings(recorder_mock, hass, loaded):
    await recorder_mock.async_add_executor_job(update_statistics_issues, hass)
    await hass.async_block_till_done()
    assert not ir.async_get(hass).issues


@pytest.mark.parametrize(
    "language,expected", [("en", "Is Raining"), ("cs", "Déšť"), ("de", "Is Raining")]
)
async def test_native_published_entity_uses_locale_without_changing_identity(
    hass, cloud, language, expected
):
    _, api = cloud
    hass.config.language = language
    entry = MockConfigEntry(domain=DOMAIN, data={"username": USERNAME, "password": PASSWORD})
    entry.add_to_hass(hass)
    with patch("custom_components.velux_active.coordinator.VeluxActiveAPI", return_value=api):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("binary_sensor", DOMAIN, "lab-gateway_is_raining")
    assert registry.async_get(entity_id).original_name == expected
    assert hass.states.get(entity_id).attributes["friendly_name"] == f"Lab Gateway {expected}"
    for suffix in ("calibrating", "silent"):
        records = [
            record
            for record in er.async_entries_for_config_entry(registry, entry.entry_id)
            if record.unique_id.endswith(f"_{suffix}")
        ]
        assert records and all(record.original_device_class is None for record in records)
