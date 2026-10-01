"""Independent synthetic legacy composite fixture, prepared before candidate setup."""

import copy

OTHER_ENTRY = "synthetic-other-entry"
COMPOSITE_ID = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


def with_composite(storage):
    result = copy.deepcopy(storage)
    other = copy.deepcopy(result["core.config_entries"]["data"]["entries"][0])
    other.update(
        entry_id=OTHER_ENTRY, domain="lab_probe", title="Synthetic other integration", data={}
    )
    result["core.config_entries"]["data"]["entries"].append(other)
    registry = result["core.device_registry"]
    registry.update(version=1, minor_version=12)
    composite = copy.deepcopy(registry["data"]["devices"][0])
    composite.update(
        id=COMPOSITE_ID,
        identifiers=[["velux_active", "absent-composite"]],
        name_by_user="Other retained device",
    )
    registry["data"]["devices"].append(composite)
    for device in registry["data"]["devices"]:
        owner = device["config_entry_id"]
        entries = [owner, OTHER_ENTRY] if device["id"] == COMPOSITE_ID else [owner]
        device["config_entries"] = entries
        device["config_entries_subentries"] = {entry: [None] for entry in entries}
        device["primary_config_entry"] = owner
        for key in (
            "config_entry_id",
            "config_subentry_id",
            "composite_device_id",
            "composite_primary_config_entry",
            "split_at",
            "has_composite_identifiers",
        ):
            device.pop(key, None)
    for record in result["core.entity_registry"]["data"]["entities"]:
        if record["unique_id"].endswith(("_wifi_strength", "_rf_strength", "_battery_level")):
            record["options"] = {"sensor": {"display_precision": 2}}
            if record["unique_id"].endswith("_battery_level"):
                record["options"]["sensor"]["unit_of_measurement"] = "V"
    entity = copy.deepcopy(result["core.entity_registry"]["data"]["entities"][0])
    entity.update(
        entity_id="sensor.other_retained",
        id="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        unique_id="other-retained",
        platform="lab_probe",
        config_entry_id=OTHER_ENTRY,
        device_id=COMPOSITE_ID,
        name="Other retained entity",
        disabled_by="user",
        options={"sensor": {"display_precision": 2}},
    )
    result["core.entity_registry"]["data"]["entities"].append(entity)
    return result
