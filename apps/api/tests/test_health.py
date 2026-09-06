from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from pmc_api.main import app


def test_health_reports_ready_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pmc_api.main.database_is_ready", lambda: True)
    monkeypatch.setattr("pmc_api.main.object_storage_is_ready", lambda: True)

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": "0.1.0",
        "dependencies": {"database": "ok", "object_storage": "ok"},
    }


def test_health_returns_503_without_exposing_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pmc_api.main.database_is_ready", lambda: False)
    monkeypatch.setattr("pmc_api.main.object_storage_is_ready", lambda: True)

    response = TestClient(app).get("/health")

    assert response.status_code == 503
    assert response.json()["dependencies"]["database"] == "unavailable"
    assert "postgresql" not in response.text.lower()
