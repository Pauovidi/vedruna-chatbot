from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from core.config import Settings, get_settings


def test_health_sanitizes_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret")
    get_settings.cache_clear()
    response = TestClient(create_app()).get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["openai_api_key_present"] is True
    assert "sk-test-secret" not in str(body)
    assert body["llm_provider"] == "openai"


def test_production_without_durable_db_fails() -> None:
    settings = Settings(APP_ENV="production", DATABASE_URL="")
    with pytest.raises(RuntimeError):
        settings.assert_production_ready()
