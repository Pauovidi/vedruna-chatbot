from __future__ import annotations

from fastapi.testclient import TestClient

from api.dependencies import (
    get_events,
    get_orchestrator,
    get_registry,
    get_retriever,
    get_state_manager,
    get_store,
)
from api.main import app
from core.config import get_settings


def _reset_dependencies() -> None:
    get_orchestrator.cache_clear()
    get_state_manager.cache_clear()
    get_events.cache_clear()
    get_store.cache_clear()
    get_registry.cache_clear()
    get_retriever.cache_clear()
    get_settings.cache_clear()


def _client(monkeypatch) -> TestClient:
    monkeypatch.setenv("ELEVENLABS_NATIVE_AGENT_ENABLED", "true")
    monkeypatch.setenv("ELEVENLABS_AGENT_API_KEY", "native-agent-test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("RPA_DRY_RUN", "true")
    monkeypatch.setenv("VOICE_TRANSFER_ENABLED", "false")
    _reset_dependencies()
    return TestClient(app)


def _turn(
    client: TestClient,
    utterance: str,
    *,
    conversation_id: str = "native-conv",
):
    return client.post(
        "/v1/agent/turn",
        headers={"Authorization": "Bearer native-agent-test-key"},
        json={"conversation_id": conversation_id, "utterance": utterance},
    )


def test_native_agent_route_requires_explicit_enablement(monkeypatch) -> None:
    monkeypatch.setenv("ELEVENLABS_NATIVE_AGENT_ENABLED", "false")
    monkeypatch.setenv("ELEVENLABS_AGENT_API_KEY", "native-agent-test-key")
    _reset_dependencies()

    response = TestClient(app).post(
        "/v1/agent/turn",
        headers={"Authorization": "Bearer native-agent-test-key"},
        json={"conversation_id": "disabled", "utterance": "hola"},
    )

    assert response.status_code == 503


def test_native_agent_turn_returns_authority_without_renderer_copy(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = _turn(client, "Hola, quiero pedir una cita")

    assert response.status_code == 200
    body = response.json()
    assert body["reply_key"] == "vedruna_ask_clinic"
    assert body["next_step"] == "collect_missing_booking_field"
    assert body["pending_fields"] == ["clinic"]
    assert "reply_text" not in body
    messages = get_state_manager().list_messages("elevenlabs-native:native-conv")
    assert [message["role"] for message in messages] == ["user"]


def test_native_agent_accepts_elevenlabs_secret_header_value(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.post(
        "/v1/agent/turn",
        headers={"Authorization": "native-agent-test-key"},
        json={"conversation_id": "native-secret", "utterance": "hola"},
    )

    assert response.status_code == 200


def test_native_agent_booking_needs_server_verified_confirmation(monkeypatch) -> None:
    client = _client(monkeypatch)
    conversation_id = "native-booking"
    for utterance in [
        "Quiero cita en Santa Isabel para una ecografia",
        "Me llamo Ana Perez",
        "600111222",
        "Tengo dolor en el talon",
        "Miercoles por la tarde",
    ]:
        response = _turn(client, utterance, conversation_id=conversation_id)
        assert response.status_code == 200

    offered = response.json()
    assert offered["reply_key"] == "vedruna_offer_slots"
    assert offered["offered_slots"]

    selected = _turn(client, "La primera", conversation_id=conversation_id)
    selected_body = selected.json()
    assert selected_body["requires_explicit_confirmation"] is True
    assert selected_body["next_step"] == "request_explicit_confirmation"
    assert selected_body["tool_results"][0]["status"] == "blocked"
    assert selected_body["tool_results"][0]["confirmation_required"] is True

    confirmed = _turn(client, "Si confirmo", conversation_id=conversation_id)
    confirmed_body = confirmed.json()
    assert confirmed_body["rpa_mode"] == "dry_run"
    assert confirmed_body["tool_results"][0]["status"] == "dry_run"
    assert confirmed_body["next_step"] == "report_dry_run_suppressed"


def test_native_agent_cannot_submit_a_verified_confirmation(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.post(
        "/v1/agent/turn",
        headers={"Authorization": "Bearer native-agent-test-key"},
        json={
            "conversation_id": "forged-confirmation",
            "utterance": "hola",
            "confirmation_verified": True,
        },
    )

    assert response.status_code == 422


def test_native_agent_santa_isabel_rejects_insurance(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = _turn(
        client,
        "Quiero cita en Santa Isabel y tengo Sanitas",
        conversation_id="native-insurance",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["reply_key"] == "vedruna_santa_isabel_particular_only"
    assert body["clinic"] == "santa_isabel"
    assert body["handoff_required"] is False
