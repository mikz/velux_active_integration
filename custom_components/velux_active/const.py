"""Constants for the velux_active integration."""

import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.util.hass_dict import HassKey
from velux_active_client import RateLimitState

LOGGER = logging.getLogger(__package__)

DOMAIN = "velux_active"
HOMEKIT_MODELS = frozenset({"VELUX Gateway", "VELUX Gateway\x00"})

_RATE_LIMIT: HassKey[RateLimitState] = HassKey("velux_active_rate_limit")


@callback
def async_rate_limit_state(hass: HomeAssistant) -> RateLimitState:
    """Retain one conservative cloud-endpoint deadline for this HA process.

    Validation can precede component setup. The state has no credentials,
    account identifiers, sessions, tasks or listeners and survives entry removal.
    """
    if _RATE_LIMIT not in hass.data:
        hass.data[_RATE_LIMIT] = RateLimitState()
    return hass.data[_RATE_LIMIT]
