"""Sign VELUX cloud window commands."""

import base64
import hashlib
import hmac
import time
from typing import Any

from .api import VeluxWindowData
from .velux_active_client.client import JSON

_last_timestamp = 0
_last_nonce = -1


def signed_window(device: VeluxWindowData, position: int, keys: dict[str, Any]) -> dict[str, JSON]:
    """Sign the VELUX force command; protocol documented by Niek/ha-velux-active."""
    key = base64.b64decode(keys["hash_sign_key"], altchars=b"-_", validate=True)
    global _last_timestamp, _last_nonce
    # VELUX rejects nanosecond-sized nonces; share a sequence across all windows.
    now = int(time.time())
    timestamp = max(now, _last_timestamp)
    nonce = _last_nonce + 1 if now <= _last_timestamp else 0
    _last_timestamp, _last_nonce = timestamp, nonce
    message = f"target_position{position}{timestamp}{nonce}{device.id}"
    signature = base64.urlsafe_b64encode(
        hmac.new(key, message.encode(), hashlib.sha512).digest()
    ).decode()
    return {
        "id": device.id,
        "bridge": device.bridge,
        "sign_key_id": keys["sign_key_id"],
        "target_position": position,
        "force": True,
        "timestamp": timestamp,
        "nonce": nonce,
        "hash_target_position": signature,
    }
