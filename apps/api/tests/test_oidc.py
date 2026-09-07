from __future__ import annotations

import base64
import json
import time
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from pmc_api.config import Settings
from pmc_api.oidc import OIDCProvider, OIDCValidationError


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _key_material() -> tuple[rsa.RSAPrivateKey, dict[str, Any]]:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private.public_key().public_numbers()
    jwk = {
        "kty": "RSA",
        "kid": "test-key",
        "use": "sig",
        "alg": "RS256",
        "n": _b64(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")),
        "e": _b64(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")),
    }
    return private, jwk


def _jwt(private: rsa.RSAPrivateKey, claims: dict[str, Any]) -> str:
    header = _b64(json.dumps({"alg": "RS256", "kid": "test-key"}).encode())
    payload = _b64(json.dumps(claims).encode())
    content = f"{header}.{payload}".encode()
    signature = private.sign(content, padding.PKCS1v15(), hashes.SHA256())
    return f"{header}.{payload}.{_b64(signature)}"


def _provider(
    token_claims: dict[str, Any], *, sign_with_wrong_key: bool = False
) -> tuple[OIDCProvider, str]:
    private, jwk = _key_material()
    signing_key = _key_material()[0] if sign_with_wrong_key else private
    settings = Settings(
        environment="test",
        oidc_issuer="https://issuer.example/realms/pm",
        oidc_discovery_url="https://internal.example/.well-known/openid-configuration",
        oidc_backchannel_base_url="https://internal.example",
        oidc_client_id="pm-client",
    )
    metadata = {
        "issuer": settings.oidc_issuer,
        "authorization_endpoint": "https://issuer.example/authorize",
        "token_endpoint": "https://issuer.example/token",
        "jwks_uri": "https://issuer.example/jwks",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("openid-configuration"):
            return httpx.Response(200, json=metadata)
        if request.url.path.endswith("jwks"):
            return httpx.Response(200, json={"keys": [jwk]})
        return httpx.Response(400)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OIDCProvider(settings, client), _jwt(signing_key, token_claims)


def _claims(**overrides: Any) -> dict[str, Any]:
    claims: dict[str, Any] = {
        "iss": "https://issuer.example/realms/pm",
        "sub": "synthetic-subject",
        "aud": "pm-client",
        "exp": int(time.time()) + 300,
        "iat": int(time.time()),
        "nonce": "expected-nonce",
        "preferred_username": "pmc-user-a",
        "email": "pmc-user-a@example.test",
    }
    claims.update(overrides)
    return claims


@pytest.mark.anyio
async def test_valid_oidc_assertion() -> None:
    provider, token = _provider(_claims())
    identity = await provider.validate_id_token(token, nonce="expected-nonce")
    assert identity.subject == "synthetic-subject"
    assert identity.email == "pmc-user-a@example.test"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "overrides",
    [
        {"iss": "https://wrong.example"},
        {"aud": "wrong-client"},
        {"exp": int(time.time()) - 120},
        {"nonce": "wrong-nonce"},
    ],
)
async def test_invalid_oidc_claims_are_denied(overrides: dict[str, Any]) -> None:
    provider, token = _provider(_claims(**overrides))
    with pytest.raises(OIDCValidationError):
        await provider.validate_id_token(token, nonce="expected-nonce")


@pytest.mark.anyio
async def test_invalid_signature_is_denied() -> None:
    provider, token = _provider(_claims(), sign_with_wrong_key=True)
    with pytest.raises(OIDCValidationError):
        await provider.validate_id_token(token, nonce="expected-nonce")


@pytest.mark.anyio
async def test_pkce_mismatch_is_denied_by_token_endpoint() -> None:
    settings = Settings(
        environment="test",
        oidc_issuer="https://issuer.example/realms/pm",
        oidc_discovery_url="https://internal.example/.well-known/openid-configuration",
        oidc_backchannel_base_url="https://internal.example",
        oidc_client_id="pm-client",
    )
    metadata = {
        "issuer": settings.oidc_issuer,
        "authorization_endpoint": "https://issuer.example/authorize",
        "token_endpoint": "https://issuer.example/token",
        "jwks_uri": "https://issuer.example/jwks",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=metadata)
        return httpx.Response(400, json={"error": "invalid_grant"})

    provider = OIDCProvider(settings, httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    with pytest.raises(httpx.HTTPStatusError):
        await provider.exchange_code(code="synthetic-code", verifier="wrong-verifier")
