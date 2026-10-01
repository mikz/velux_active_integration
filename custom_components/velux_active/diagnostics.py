"""Allowlisted config-entry health; never export provider strings or identities."""

from math import isfinite
from time import monotonic

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .coordinator import VeluxActiveConfigEntry


def observation_age(observed: float | None) -> float | None:
    """Only finite, nonnegative relative timing is safe and meaningful."""
    if observed is None or not isfinite(observed):
        return None
    age = monotonic() - observed
    return round(age, 3) if isfinite(age) and age >= 0 else None


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: VeluxActiveConfigEntry
) -> dict[str, object]:
    """Return only owned JSON; HA owns its enclosing wrapper and filename."""
    loaded = entry.state is ConfigEntryState.LOADED
    result: dict[str, object] = {"loaded": loaded, "schema_version": 1}
    if not loaded:
        return result
    coordinator = entry.runtime_data
    supported_counts = {"gateway": 0, "window": 0, "shutter": 0, "sensor": 0}
    known = {"NXG": "gateway", "NXS": "sensor", "NXD": "sensor"}
    # Type labels originate in provider data. Only known enums are exported.
    for home in coordinator.data.values():
        for device in home["devices"]:
            if device.type in known:
                supported_counts[known[device.type]] += 1
            elif device.type == "NXO":
                kind: object = getattr(device, "velux_type", None)
                if kind in ("window", "shutter"):
                    supported_counts[str(kind)] += 1
    result.update(
        {
            "status_success": coordinator.last_update_success,
            "topology_initialized": coordinator.topology_observed_at is not None,
            "topology_failed": coordinator.topology_failed,
            "refresh_in_progress": coordinator.refreshing,
            "home_count": len(coordinator.homes or []),
            "inventory_count": len(coordinator.api.inventory_ids),
            "supported_model_counts": supported_counts,
            "topology_age_seconds": observation_age(coordinator.topology_observed_at),
            "status_age_seconds": observation_age(coordinator.status_observed_at),
            "topology_attempt_age_seconds": observation_age(coordinator.topology_attempted_at),
            "status_interval_seconds": 60,
            "topology_interval_seconds": 300,
        }
    )
    return result
