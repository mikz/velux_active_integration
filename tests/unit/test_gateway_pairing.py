"""Synthetic Netcom peer exercises framing, key exchange and failure handling."""

import base64
import hashlib
import struct
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519

from custom_components.velux_active.velux_active_client import pairing as p


class Peer:
    def __init__(self, *args):
        self.queue = []
        self.closed = False
        self.private = x25519.X25519PrivateKey.generate()
        self.key = bytes(range(32))
        self.secure = None
        self.challenge_verified = False

    def close(self):
        self.closed = True

    def send(self, raw):
        kind, size = struct.unpack("<HH", raw[:4])
        assert len(raw[4:]) == size
        if kind == p.FRAME_PING:
            self.queue.append(p._Frame(p.FRAME_PONG, b""))
        elif kind == p.FRAME_ECDH_REQUEST:
            peer = x25519.X25519PublicKey.from_public_bytes(raw[5:])
            self.secure = p._SecureContext(
                hashlib.sha512(self.private.exchange(peer)).digest()[:32]
            )
            public = self.private.public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw
            )
            self.queue.append(p._Frame(p.FRAME_ECDH_RESPONSE, b"\x01" + public))
        else:
            assert kind == p.FRAME_SECURE
            frame = self.secure.decrypt_payload(raw[4:])
            kind, size = struct.unpack("<HH", frame[:4])
            body = frame[4:]
            assert len(body) == size
            if kind == p.FRAME_END_TO_END_KEY_REQUEST:
                self.key_id = body[1:]
                response = p._pack_frame(p.FRAME_END_TO_END_KEY_RESPONSE, b"\x00" + self.key)
            elif kind == p.FRAME_END_TO_END_NONCE_REQUEST:
                response = p._pack_frame(p.FRAME_END_TO_END_NONCE_RESPONSE, b"synthetic-nonce")
            elif kind == p.FRAME_END_TO_END_CHALLENGE_REQUEST:
                assert (
                    body
                    == self.key_id
                    + hashlib.sha512(self.key_id + self.key + b"synthetic-nonce").digest()
                )
                self.challenge_verified = True
                response = p._pack_frame(p.FRAME_END_TO_END_CHALLENGE_RESPONSE, b"\x00")
            else:
                assert kind == p.FRAME_CLOSE
                return
            encrypted = self.secure.encrypt_frame(response)
            self.queue.append(p._Frame(p.FRAME_SECURE, encrypted[4:]))

    def recv_frame(self):
        return self.queue.pop(0)


def test_complete_gateway_handshake(monkeypatch):
    peer = Peer()
    monkeypatch.setattr(p, "_NetcomSocket", lambda *args: peer)
    monkeypatch.setattr(p, "_tcp_open", lambda *args: True)
    key = p.retrieve_signing_key(host="synthetic.invalid")
    assert base64.urlsafe_b64decode(key.hash_sign_key) == peer.key
    assert base64.urlsafe_b64decode(key.sign_key_id) == peer.key_id
    assert peer.closed and peer.challenge_verified


def test_socket_framing_and_eof(monkeypatch):
    socket = Mock()
    frame = p._pack_frame(42, b"abc")
    socket.recv.side_effect = [frame[:2], frame[2:5], frame[5:], b""]
    monkeypatch.setattr(p.socket, "create_connection", lambda *a, **kw: socket)
    connection = p._NetcomSocket("synthetic.invalid", 25050, 10)
    assert connection.recv_frame() == p._Frame(42, b"abc")
    connection.send(b"hello")
    socket.sendall.assert_called_once_with(b"hello")
    with pytest.raises(p.VeluxPairingError, match="closed"):
        connection.recv_frame()
    connection._deadline = 0
    with pytest.raises(p.VeluxPairingError, match="timed out"):
        connection.recv_frame()
    connection.close()
    socket.close.assert_called_once()


@pytest.mark.parametrize("payload", [b"", b"\x01", b"\x02", b"\x03", b"\xff", b"\x00short"])
def test_invalid_key_response(monkeypatch, payload):
    monkeypatch.setattr(p, "_receive_secure_payload", lambda *a: payload)
    with pytest.raises(p.VeluxPairingError):
        p._request_end_to_end_key(Mock(), Mock(), b"key")


@pytest.mark.parametrize(
    "payloads",
    [[b""], [b"nonce", b""], [b"nonce", b"\x01"], [b"nonce", b"\x02"], [b"nonce", b"\xff"]],
)
def test_invalid_challenge(monkeypatch, payloads):
    responses = iter(payloads)
    monkeypatch.setattr(p, "_receive_secure_payload", lambda *a: next(responses))
    with pytest.raises(p.VeluxPairingError):
        p._verify_end_to_end_key(Mock(), Mock(), b"key-id", b"key")


@pytest.mark.parametrize(
    "decrypted", [b"", b"abc", struct.pack("<HH", 42, 2) + b"x", p._pack_frame(43, b"x")]
)
def test_invalid_secure_frame(decrypted):
    sock = Mock()
    sock.recv_frame.return_value = p._Frame(p.FRAME_SECURE, b"ciphertext")
    secure = Mock()
    secure.decrypt_payload.return_value = decrypted
    with pytest.raises(p.VeluxPairingError):
        p._receive_secure_payload(sock, secure, 42, "test")


def test_ping_and_unexpected_frame():
    sock = Mock()
    sock.recv_frame.side_effect = [
        p._Frame(p.FRAME_PING, b""),
        p._Frame(42, b"answer"),
        p._Frame(43, b""),
    ]
    assert p._expect_frame(sock, {42}, "test").payload == b"answer"
    sock.send.assert_called_once_with(p._pack_frame(p.FRAME_PONG))
    with pytest.raises(p.VeluxPairingError):
        p._expect_frame(sock, {42}, "test")


@pytest.mark.parametrize("pong,public", [(b"bad", b""), (b"", b"bad")])
def test_invalid_exchange(pong, public):
    sock = Mock()
    sock.recv_frame.side_effect = [
        p._Frame(p.FRAME_PONG, pong),
        p._Frame(p.FRAME_ECDH_RESPONSE, public),
    ]
    with pytest.raises(p.VeluxPairingError):
        p._perform_ecdh(sock)


def test_nonce_rollover_and_authenticated_encryption():
    nonce = bytearray(b"\x00" * 11 + b"\xff")
    p._increment_nonce(nonce)
    assert nonce == bytearray(b"\x00" * 10 + b"\x01\x00")
    nonce = bytearray(b"\x00" * 4 + b"\xff" * 8)
    p._increment_nonce(nonce)
    assert nonce == bytearray(12)
    left, right = p._SecureContext(bytes(32)), p._SecureContext(bytes(32))
    encrypted = left.encrypt_frame(b"test")[4:]
    assert right.decrypt_payload(encrypted) == b"test"
    with pytest.raises(InvalidTag):
        right.decrypt_payload(encrypted)


@pytest.mark.parametrize("exception", [False, True])
def test_pairing_timeout(monkeypatch, exception):
    clock = iter([0, 0, 31])
    monkeypatch.setattr(
        p, "time", SimpleNamespace(monotonic=lambda: next(clock), sleep=lambda _: None)
    )
    monkeypatch.setattr(p, "_tcp_open", lambda *a: exception)

    def fail(*a):
        raise OSError("synthetic")

    monkeypatch.setattr(p, "_request_signing_key", fail)
    with pytest.raises(p.VeluxPairingError):
        p.retrieve_signing_key(host="synthetic.invalid")


def test_tcp_probe(monkeypatch):
    class Socket:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    monkeypatch.setattr(p.socket, "create_connection", lambda *a, **kw: Socket())
    assert p._tcp_open("synthetic.invalid", 25050)

    def fail(*a, **kw):
        raise OSError("synthetic")

    monkeypatch.setattr(p.socket, "create_connection", fail)
    assert not p._tcp_open("synthetic.invalid", 25050)
