"""Window signatures use small, unique nonce sequences across all covers."""

import base64
import hashlib
import hmac
from types import SimpleNamespace

from custom_components.velux_active import signing


def test_nonce_sequence_across_windows_and_clock_changes(monkeypatch):
    monkeypatch.setattr(signing, "_last_timestamp", 0)
    monkeypatch.setattr(signing, "_last_nonce", -1)
    times = iter([1000.9, 1000.95, 1001.1, 999.0, 1002.0])
    monkeypatch.setattr(signing, "time", SimpleNamespace(time=lambda: next(times)))
    key = bytes(range(32))
    keys = {"hash_sign_key": base64.urlsafe_b64encode(key).decode(), "sign_key_id": "key"}
    for index, expected in enumerate([(1000, 0), (1000, 1), (1001, 0), (1001, 1), (1002, 0)]):
        device = SimpleNamespace(id=f"window-{index % 3}", bridge="gateway")
        module = signing.signed_window(device, 7, keys)
        assert (module["timestamp"], module["nonce"]) == expected
        timestamp, nonce = expected
        message = f"target_position7{timestamp}{nonce}{device.id}"
        assert (
            module["hash_target_position"]
            == base64.urlsafe_b64encode(
                hmac.new(key, message.encode(), hashlib.sha512).digest()
            ).decode()
        )
