from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Any, cast
from urllib.parse import urlencode, urlsplit, urlunsplit

import httpx
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet
from joserfc.jwt import JWTClaimsRegistry

from pmc_api.config import Settings


class OIDCValidationError(ValueError):
    pass


@dataclass(frozen=True)
class IdentityClaims:
    issuer: str
    subject: str
    display_name: str
    email: str | None


class OIDCProvider:
    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self.settings = settings
        self._client = client

    def _backchannel_url(self, public_url: str) -> str:
        if not self.settings.oidc_backchannel_base_url:
            return public_url
        public = urlsplit(public_url)
        internal = urlsplit(self.settings.oidc_backchannel_base_url)
        return urlunsplit((internal.scheme, internal.netloc, public.path, public.query, ""))

    async def discovery(self) -> dict[str, Any]:
        response = await self._client.get(self.settings.oidc_discovery_url)
        response.raise_for_status()
        metadata = cast(dict[str, Any], response.json())
        if metadata.get("issuer") != self.settings.oidc_issuer:
            raise OIDCValidationError("OIDC discovery issuer mismatch")
        for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
            if not isinstance(metadata.get(key), str):
                raise OIDCValidationError(f"OIDC discovery missing {key}")
        return metadata

    async def authorization_url(self, *, state: str, nonce: str, challenge: str) -> str:
        metadata = await self.discovery()
        query = urlencode(
            {
                "client_id": self.settings.oidc_client_id,
                "redirect_uri": self.settings.oidc_callback_url,
                "response_type": "code",
                "scope": "openid profile email",
                "state": state,
                "nonce": nonce,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"{metadata['authorization_endpoint']}?{query}"

    async def exchange_code(self, *, code: str, verifier: str) -> str:
        metadata = await self.discovery()
        response = await self._client.post(
            self._backchannel_url(metadata["token_endpoint"]),
            data={
                "grant_type": "authorization_code",
                "client_id": self.settings.oidc_client_id,
                "redirect_uri": self.settings.oidc_callback_url,
                "code": code,
                "code_verifier": verifier,
            },
        )
        response.raise_for_status()
        token_data = response.json()
        id_token = token_data.get("id_token")
        if not isinstance(id_token, str):
            raise OIDCValidationError("OIDC token response omitted id_token")
        return id_token

    async def validate_id_token(self, encoded_token: str, *, nonce: str) -> IdentityClaims:
        metadata = await self.discovery()
        response = await self._client.get(self._backchannel_url(metadata["jwks_uri"]))
        response.raise_for_status()
        try:
            token = jwt.decode(
                encoded_token,
                KeySet.import_key_set(response.json()),
                algorithms=["RS256", "PS256", "ES256"],
            )
            claims = token.claims
            registry = JWTClaimsRegistry(
                leeway=30,
                iss={"essential": True, "value": self.settings.oidc_issuer},
                sub={"essential": True},
                aud={"essential": True, "value": self.settings.oidc_client_id},
                exp={"essential": True},
                nonce={"essential": True},
            )
            registry.validate(claims)
        except (JoseError, ValueError, TypeError) as exc:
            raise OIDCValidationError("OIDC assertion validation failed") from exc
        if not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
            raise OIDCValidationError("OIDC nonce mismatch")
        subject = str(claims["sub"])
        display_name = str(claims.get("name") or claims.get("preferred_username") or subject)
        email = claims.get("email")
        return IdentityClaims(
            issuer=str(claims["iss"]),
            subject=subject,
            display_name=display_name[:160],
            email=str(email)[:320] if email else None,
        )
