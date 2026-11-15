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


@pytest.mark.parametrize("field", ["web_url", "oidc_issuer", "oidc_callback_url"])
@pytest.mark.parametrize("suffix", ["?", "#", "\n", "\t", "\x00", " "])
def test_production_rejects_controls_and_empty_decorations(field: str, suffix: str) -> None:
    data = production_config()
    data[field] = str(data[field]) + suffix
    with pytest.raises(ValueError):
        Settings.model_validate(data)


@pytest.mark.parametrize(
    "url",
    [
        "https://bad host.example.test",
        "https://host\\other.test",
        "https://[bad::address]",
        "https://qms.example.test:0",
        "https://qms.example.test:65536",
        "https://qms.example.test:-1",
        "https://@qms.example.test",
    ],
)
def test_production_rejects_malformed_host_and_ports(url: str) -> None:
    data = production_config()
    data["web_url"] = url
    with pytest.raises(ValueError):
        Settings.model_validate(data)


@pytest.mark.parametrize(
    ("url", "origin"),
    [
        ("HTTPS://QMS.EXAMPLE.TEST:443/", "https://qms.example.test"),
        ("https://qms.example.test:8443/", "https://qms.example.test:8443"),
        ("https://[2001:0db8::1]:443/", "https://[2001:db8::1]"),
    ],
)
def test_web_origin_matches_browser_normalization_without_changing_oidc(
    url: str, origin: str
) -> None:
    data = production_config()
    data["web_url"] = url
    data["oidc_issuer"] = "https://LOGIN.example.test:443/realms/PerfectMatch"
    data["oidc_callback_url"] = "https://API.example.test:443/auth/Callback"
    result = Settings.model_validate(data)
    assert result.web_url == origin
    assert result.oidc_issuer == data["oidc_issuer"]
    assert result.oidc_callback_url == data["oidc_callback_url"]


def test_validation_error_text_does_not_print_sensitive_input() -> None:
    data = production_config()
    marker = "synthetic-sensitive-input-marker"
    data["web_url"] = {"private": marker}
    with pytest.raises(ValueError) as raised:
        Settings.model_validate(data)
    assert marker not in str(raised.value)
    assert str(data["login_transaction_key"]) not in str(raised.value)


@pytest.mark.parametrize("key", ["configured", " ", "invalid-key", "non-ascii-ñ"])
def test_production_rejects_unusable_login_encryption_key(key: str) -> None:
    data = production_config()
    data["login_transaction_key"] = key
    with pytest.raises(ValueError, match="encryption key"):
        Settings.model_validate(data)
