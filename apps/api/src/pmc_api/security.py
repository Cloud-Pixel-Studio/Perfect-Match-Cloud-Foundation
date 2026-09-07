from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken

SESSION_TOKEN_BYTES = 32


def generate_token(byte_count: int = SESSION_TOKEN_BYTES) -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(byte_count)).rstrip(b"=").decode("ascii")


def token_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode("ascii")).digest()


def token_matches(token: str, expected_hash: bytes) -> bool:
    return hmac.compare_digest(token_hash(token), expected_hash)


@dataclass(frozen=True)
class PKCEPair:
    verifier: str
    challenge: str


def generate_pkce() -> PKCEPair:
    verifier = generate_token(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
    return PKCEPair(verifier=verifier, challenge=challenge.rstrip(b"=").decode("ascii"))


class TransactionCipher:
    def __init__(self, key: str) -> None:
        if not key:
            raise ValueError("login transaction encryption key is required")
        self._cipher = Fernet(key.encode("ascii"))

    def encrypt(self, value: str) -> bytes:
        return self._cipher.encrypt(value.encode("utf-8"))

    def decrypt(self, value: bytes) -> str:
        try:
            return self._cipher.decrypt(value).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("invalid protected login transaction") from exc
