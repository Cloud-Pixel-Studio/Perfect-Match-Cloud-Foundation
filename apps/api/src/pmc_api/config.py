from __future__ import annotations

from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PMC_", case_sensitive=False)

    app_version: str = "0.5.0"
    environment: Literal["development", "test", "production"] = "development"
    database_url: str = Field(
        default="postgresql+pg8000://pmcloud_app@postgres:5432/pmcloud_dev",
        repr=False,
    )
    oidc_issuer: str = "http://127.0.0.1:8080/realms/perfect-match"
    oidc_discovery_url: str = (
        "http://keycloak:8080/realms/perfect-match/.well-known/openid-configuration"
    )
    oidc_backchannel_base_url: str = "http://keycloak:8080"
    oidc_client_id: str = "perfect-match-web"
    oidc_callback_url: str = "http://127.0.0.1:8000/auth/callback"
    web_url: str = "http://127.0.0.1:3000"
    login_transaction_key: str = Field(default="", repr=False)
    login_cookie_name: str = "pm_login"
    session_cookie_name: str = "pm_session"
    csrf_cookie_name: str = "pm_csrf"
    cookie_secure: bool = False
    session_ttl_seconds: int = 28_800
    login_ttl_seconds: int = 300
    s3_endpoint: str = "http://seaweedfs:8333"
    s3_access_key: str = Field(default="", repr=False)
    s3_secret_key: str = Field(default="", repr=False)
    s3_region: str = "us-east-1"
    s3_documents_bucket: str = "pmcloud-private-documents"
    clamav_host: str = "clamav"
    clamav_port: int = Field(default=3310, ge=1, le=65535)
    clamav_timeout_seconds: float = Field(default=30, gt=0, le=120)
    clamav_signature_max_age_seconds: int = Field(default=172800, ge=3600, le=604800)

    @model_validator(mode="after")
    def validate_security_configuration(self) -> Settings:
        if self.environment == "production":
            if not self.cookie_secure:
                raise ValueError("production requires Secure session cookies")
            if not self.login_transaction_key:
                raise ValueError("production requires a login transaction encryption key")
            for field_name in ("web_url", "oidc_issuer", "oidc_callback_url"):
                address = getattr(self, field_name)
                parts = urlsplit(address)
                if (
                    parts.scheme != "https"
                    or not parts.hostname
                    or parts.username is not None
                    or parts.password is not None
                    or parts.fragment
                    or parts.query
                ):
                    raise ValueError(
                        f"production requires HTTPS {field_name} without URL credentials, query or fragment"
                    )
                try:
                    parts.port  # Reject malformed ports rather than accepting invalid public URLs.
                except ValueError as exc:
                    raise ValueError(f"production requires valid HTTPS {field_name}") from exc
                if field_name == "web_url" and parts.path not in {"", "/"}:
                    raise ValueError("production web_url must be a public origin, not a path")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
