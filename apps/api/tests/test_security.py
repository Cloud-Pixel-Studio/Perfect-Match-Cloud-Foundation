from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from starlette.requests import Request

from pmc_api.auth import AuthenticatedSession, require_csrf
from pmc_api.config import Settings
from pmc_api.models import ApplicationSession, User
from pmc_api.security import (
    SESSION_TOKEN_BYTES,
    TransactionCipher,
    generate_pkce,
    generate_token,
    token_hash,
    token_matches,
)


def test_session_token_has_256_bits_and_only_hash_is_retained() -> None:
    raw = generate_token()
    digest = token_hash(raw)
    assert len(digest) == SESSION_TOKEN_BYTES
    assert raw.encode() not in digest
    assert token_matches(raw, digest)
    assert not token_matches(generate_token(), digest)


def test_pkce_s256_and_transaction_encryption() -> None:
    pair = generate_pkce()
    cipher = TransactionCipher(Fernet.generate_key().decode())
    encrypted = cipher.encrypt(pair.verifier)
    assert pair.verifier.encode() not in encrypted
    assert cipher.decrypt(encrypted) == pair.verifier
    assert pair.challenge != pair.verifier


def _authenticated(csrf: str) -> AuthenticatedSession:
    now = datetime.now(UTC)
    user_id = uuid4()
    session_token = generate_token()
    return AuthenticatedSession(
        token=session_token,
        user=User(id=user_id, display_name="Synthetic user", status="active", created_at=now),
        record=ApplicationSession(
            id=uuid4(),
            user_id=user_id,
            token_hash=token_hash(session_token),
            csrf_token_hash=token_hash(csrf),
            created_at=now,
            expires_at=now + timedelta(hours=1),
            last_seen_at=now,
        ),
    )


def _request(origin: str = "http://127.0.0.1:3000") -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/auth/logout",
            "headers": [(b"origin", origin.encode())],
        }
    )


@pytest.mark.parametrize(
    ("header", "cookie"),
    [(None, None), ("wrong", "wrong"), ("valid", "wrong"), ("wrong", "valid")],
)
def test_csrf_denies_missing_or_invalid_tokens(header: str | None, cookie: str | None) -> None:
    with pytest.raises(HTTPException) as denied:
        require_csrf(
            _request(), _authenticated("valid"), Settings(environment="test"), header, cookie
        )
    assert denied.value.status_code == 403


def test_csrf_accepts_session_bound_token_and_rejects_wrong_origin() -> None:
    require_csrf(
        _request(), _authenticated("valid"), Settings(environment="test"), "valid", "valid"
    )
    with pytest.raises(HTTPException) as denied:
        require_csrf(
            _request("https://untrusted.example"),
            _authenticated("valid"),
            Settings(environment="test"),
            "valid",
            "valid",
        )
    assert denied.value.status_code == 403


def test_production_refuses_insecure_cookie_configuration() -> None:
    with pytest.raises(ValueError, match="Secure session cookies"):
        Settings(environment="production", cookie_secure=False, login_transaction_key="configured")
