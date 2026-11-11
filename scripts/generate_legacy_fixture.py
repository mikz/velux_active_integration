#!/usr/bin/env python3
"""Maintenance helper: uv run pytest scripts/generate_legacy_fixture.py -q.

Generate synthetic pre-candidate storage with the native pytest HA lifecycle.
"""

import asyncio
import json
from pathlib import Path

from homeassistant import config_entries
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.json import json_bytes
from pytest_homeassistant_custom_component.common import MockConfigEntry

ROOT = Path(__file__).resolve().parents[1]


async def test_generate_synthetic_storage(hass):
    fixture = json.loads(
        await asyncio.to_thread((ROOT / "tests/fixtures/legacy_v1.json").read_text)
    )
    entry = MockConfigEntry(
        domain="velux_active",
        entry_id=fixture["entry_id"],
        version=1,
        title="Synthetic legacy account",
        data={"username": "lab@example.invalid", "password": "synthetic-lab-password"},
    )
    entry.add_to_hass(hass)
    devices, entities = dr.async_get(hass), er.async_get(hass)
    ids = {}
    for item in fixture["entities"]:
        if item["device"] not in ids:
            device = devices.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers={("velux_active", item["device"])},
                name="Legacy device",
            )
            devices.async_update_device(device.id, name_by_user="My " + item["device"])
            ids[item["device"]] = device.id
        entity = entities.async_get_or_create(
            item["domain"],
            "velux_active",
            item["unique_id"],
            config_entry=entry,
            device_id=ids[item["device"]],
            suggested_object_id=item["entity_id"].split(".", 1)[1],
        )
        entities.async_update_entity(
            entity.entity_id,
            name=item["name"],
            disabled_by=er.RegistryEntryDisabler.USER if item["disabled"] else None,
        )
    stores = {
        "core.config_entries": (
            config_entries.STORAGE_VERSION,
            config_entries.STORAGE_VERSION_MINOR,
            hass.config_entries._data_to_save(),
        ),
        "core.device_registry": (
            dr.STORAGE_VERSION_MAJOR,
            dr.STORAGE_VERSION_MINOR,
            devices._data_to_save(),
        ),
        "core.entity_registry": (
            er.STORAGE_VERSION_MAJOR,
            er.STORAGE_VERSION_MINOR,
            entities._data_to_save(),
        ),
    }
    payload = {
        key: {"version": major, "minor_version": minor, "key": key, "data": data}
        for key, (major, minor, data) in stores.items()
    }
    encoded = json_bytes(payload).decode()
    await asyncio.to_thread(
        (ROOT / "tests/fixtures/legacy_storage.json").write_text, encoded + "\n"
    )
