from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PMC_", case_sensitive=False)

    app_version: str = "0.2.0"
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
    session_cookie_name: str = "pm_session"
    csrf_cookie_name: str = "pm_csrf"
    cookie_secure: bool = False
    session_ttl_seconds: int = 28_800
    login_ttl_seconds: int = 300
    s3_endpoint: str = "http://seaweedfs:8333"
    s3_access_key: str = Field(default="", repr=False)
    s3_secret_key: str = Field(default="", repr=False)
    s3_region: str = "us-east-1"

    @model_validator(mode="after")
    def validate_security_configuration(self) -> Settings:
        if self.environment == "production":
            if not self.cookie_secure:
                raise ValueError("production requires Secure session cookies")
            if not self.login_transaction_key:
                raise ValueError("production requires a login transaction encryption key")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
