from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import api.main as main_module
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
    assert body["elevenlabs_native_agent_enabled"] is False
    assert body["elevenlabs_agent_api_key_present"] is False


def test_production_without_durable_db_fails() -> None:
    settings = Settings(APP_ENV="production", DATABASE_URL="")
    with pytest.raises(RuntimeError):
        settings.assert_production_ready()


def test_app_warms_orchestrator_before_serving(monkeypatch: pytest.MonkeyPatch) -> None:
    warmed: list[bool] = []

    monkeypatch.setattr(main_module, "get_orchestrator", lambda: warmed.append(True))

    with TestClient(create_app()) as client:
        assert warmed == [True]
        assert client.get("/healthz").status_code == 200
