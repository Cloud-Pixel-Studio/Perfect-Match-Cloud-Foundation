"""Production public URL gates; development loopback defaults remain supported."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from pmc_api.config import Settings


def production_config() -> dict[str, object]:
    return {
        "environment": "production",
        "cookie_secure": True,
        "login_transaction_key": Fernet.generate_key().decode("ascii"),
        "web_url": "https://qms.example.test",
        "oidc_issuer": "https://login.example.test/realms/perfect-match",
        "oidc_callback_url": "https://api.example.test/auth/callback",
    }


def test_production_accepts_https_public_origins() -> None:
    settings = Settings.model_validate(production_config())
    assert settings.environment == "production"
    assert settings.web_url == "https://qms.example.test"


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("web_url", "http://qms.example.test"),
        ("oidc_issuer", "http://login.example.test/realms/perfect-match"),
        ("oidc_callback_url", "http://api.example.test/auth/callback"),
        ("web_url", "https://username:password@qms.example.test"),
        ("oidc_issuer", "https://login.example.test/realms/perfect-match#fragment"),
        ("oidc_callback_url", "https://api.example.test/auth/callback?token=invalid"),
        ("web_url", "https://qms.example.test:invalid"),
    ],
)
def test_production_rejects_insecure_or_invalid_public_url(setting: str, value: str) -> None:
    data = production_config()
    data[setting] = value
    with pytest.raises(ValueError, match=f"HTTPS {setting}"):
        Settings.model_validate(data)


def test_production_rejects_web_url_path() -> None:
    data = production_config()
    data["web_url"] = "https://qms.example.test/application"
    with pytest.raises(ValueError, match="web_url must be a public origin"):
        Settings.model_validate(data)


def test_development_preserves_loopback_urls() -> None:
    settings = Settings(environment="development")
    assert settings.web_url == "http://127.0.0.1:3000"
