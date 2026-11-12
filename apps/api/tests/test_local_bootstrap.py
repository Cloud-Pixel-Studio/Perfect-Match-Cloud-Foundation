from __future__ import annotations

import pytest

from pmc_api import local_identity_bootstrap


@pytest.mark.parametrize("environment", [None, "production", "staging"])
def test_local_owner_fixture_cannot_be_seeded_outside_development(
    monkeypatch: pytest.MonkeyPatch, environment: str | None
) -> None:
    if environment is None:
        monkeypatch.delenv("PMC_ENVIRONMENT", raising=False)
    else:
        monkeypatch.setenv("PMC_ENVIRONMENT", environment)

    def unexpected() -> None:
        pytest.fail("identity provider must not be touched outside development")

    monkeypatch.setattr(local_identity_bootstrap, "_configure_keycloak", unexpected)
    with pytest.raises(RuntimeError, match="development environment"):
        local_identity_bootstrap.main()
