"""Compatibility imports for the separately versioned local read-only client."""

from velux_active_client import (
    APIConnectionError,
    AuthToken,
    InvalidAuthError,
    RateLimitError,
    VeluxActiveAPI,
    VeluxDevice,
    VeluxGatewayData,
    VeluxHome,
    VeluxModule,
    VeluxShutterData,
    VeluxSwitchData,
    VeluxWindowData,
    device_from_module,
)

__all__ = [
    "APIConnectionError",
    "AuthToken",
    "InvalidAuthError",
    "RateLimitError",
    "VeluxActiveAPI",
    "VeluxDevice",
    "VeluxGatewayData",
    "VeluxHome",
    "VeluxModule",
    "VeluxShutterData",
    "VeluxSwitchData",
    "VeluxWindowData",
    "device_from_module",
]
