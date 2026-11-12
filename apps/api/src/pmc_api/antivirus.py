"""Fail-closed ClamD client using its private INSTREAM protocol."""

from __future__ import annotations

import socket
import struct
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import BinaryIO

from pmc_api.config import get_settings

MAX_REPLY_BYTES = 4096
CHUNK_BYTES = 64 * 1024


class ScanUnavailable(RuntimeError):
    """The scanner or its signature database cannot be trusted for a decision."""


class ScanVerdict(StrEnum):
    CLEAN = "clean"
    INFECTED = "infected"


def _request(command: bytes, payload: BinaryIO | None = None) -> str:
    settings = get_settings()
    try:
        with socket.create_connection(
            (settings.clamav_host, settings.clamav_port),
            timeout=settings.clamav_timeout_seconds,
        ) as connection:
            connection.settimeout(settings.clamav_timeout_seconds)
            connection.sendall(b"z" + command + b"\0")
            if payload is not None:
                while chunk := payload.read(CHUNK_BYTES):
                    connection.sendall(struct.pack("!I", len(chunk)))
                    connection.sendall(chunk)
                connection.sendall(b"\0\0\0\0")
            reply = bytearray()
            while b"\0" not in reply:
                part = connection.recv(1024)
                if not part or len(reply) + len(part) > MAX_REPLY_BYTES:
                    raise ScanUnavailable("scanner returned an incomplete or oversized response")
                reply.extend(part)
            if reply[-1] != 0 or reply.count(0) != 1:
                raise ScanUnavailable("scanner returned an invalid response frame")
            return reply[:-1].decode("ascii", errors="strict")
    except ScanUnavailable:
        raise
    except (OSError, UnicodeError, struct.error) as error:
        raise ScanUnavailable("scanner is unavailable") from error


def _check_signature_freshness() -> None:
    reply = _request(b"VERSION")
    try:
        fields = reply.split("/", maxsplit=2)
        if len(fields) != 3 or not fields[0].startswith("ClamAV "):
            raise ValueError("unexpected ClamD VERSION response")
        signature_date = datetime.strptime(fields[2], "%a %b %d %H:%M:%S %Y").replace(tzinfo=UTC)
        now = datetime.now(UTC)
        if signature_date > now + timedelta(hours=24):
            raise ValueError("scanner signature timestamp is in the future")
        if now - signature_date > timedelta(
            seconds=get_settings().clamav_signature_max_age_seconds
        ):
            raise ValueError("scanner signatures are stale")
    except ValueError as error:
        raise ScanUnavailable("scanner signature freshness could not be verified") from error


def scanner_is_ready() -> bool:
    try:
        _check_signature_freshness()
        return _request(b"PING") == "PONG"
    except ScanUnavailable:
        return False


def scan(payload: BinaryIO) -> ScanVerdict:
    _check_signature_freshness()
    payload.seek(0)
    reply = _request(b"INSTREAM", payload)
    if reply == "stream: OK":
        return ScanVerdict.CLEAN
    if reply.startswith("stream: ") and reply.endswith(" FOUND"):
        return ScanVerdict.INFECTED
    raise ScanUnavailable("scanner did not return a recognized file verdict")
