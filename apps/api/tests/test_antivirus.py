from __future__ import annotations

import io
import socket
import struct
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from pmc_api import antivirus


class FakeSocket:
    def __init__(self, reply: bytes) -> None:
        self.reply = reply
        self.sent = bytearray()

    def __enter__(self) -> FakeSocket:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def settimeout(self, _timeout: float) -> None:
        return None

    def sendall(self, payload: bytes) -> None:
        self.sent.extend(payload)

    def recv(self, _size: int) -> bytes:
        reply, self.reply = self.reply, b""
        return reply


def _version(timestamp: datetime | None = None) -> bytes:
    moment = timestamp or datetime.now(UTC)
    return f"ClamAV 1.5.4/30001/{moment.strftime('%a %b %d %H:%M:%S %Y')}\0".encode()


def _connections(monkeypatch: pytest.MonkeyPatch, *replies: bytes) -> list[FakeSocket]:
    sockets = [FakeSocket(reply) for reply in replies]
    pending = iter(sockets)
    monkeypatch.setattr(
        antivirus,
        "get_settings",
        lambda: SimpleNamespace(
            clamav_host="clamav",
            clamav_port=3310,
            clamav_timeout_seconds=2,
            clamav_signature_max_age_seconds=172800,
        ),
    )
    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: next(pending))
    return sockets


def test_clean_scan_streams_bytes_with_framing_and_fresh_signatures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sockets = _connections(monkeypatch, _version(), b"stream: OK\0")
    payload = b"%PDF-test payload"

    verdict = antivirus.scan(io.BytesIO(payload))

    assert verdict is antivirus.ScanVerdict.CLEAN
    assert sockets[0].sent == b"zVERSION\0"
    assert sockets[1].sent == (
        b"zINSTREAM\0" + struct.pack("!I", len(payload)) + payload + b"\0\0\0\0"
    )


def test_infected_scan_returns_rejected_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    _connections(monkeypatch, _version(), b"stream: Eicar-Signature FOUND\0")

    assert antivirus.scan(io.BytesIO(b"%PDF-test")) is antivirus.ScanVerdict.INFECTED


def test_stale_signatures_fail_closed_before_scanning(monkeypatch: pytest.MonkeyPatch) -> None:
    stale = datetime.now(UTC).replace(year=datetime.now(UTC).year - 1)
    sockets = _connections(monkeypatch, _version(stale))

    with pytest.raises(antivirus.ScanUnavailable):
        antivirus.scan(io.BytesIO(b"%PDF-test"))

    assert len(sockets) == 1


def test_unrecognized_scanner_response_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    _connections(monkeypatch, _version(), b"stream: ERROR\0")

    with pytest.raises(antivirus.ScanUnavailable):
        antivirus.scan(io.BytesIO(b"%PDF-test"))


def test_unavailable_scanner_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        antivirus,
        "get_settings",
        lambda: SimpleNamespace(
            clamav_host="clamav",
            clamav_port=3310,
            clamav_timeout_seconds=1,
            clamav_signature_max_age_seconds=172800,
        ),
    )

    def fail_connection(*_args: object, **_kwargs: object) -> FakeSocket:
        raise OSError("connection refused")

    monkeypatch.setattr(socket, "create_connection", fail_connection)
    with pytest.raises(antivirus.ScanUnavailable):
        antivirus.scan(io.BytesIO(b"%PDF-test"))
