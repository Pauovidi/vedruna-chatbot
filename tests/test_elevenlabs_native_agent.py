from __future__ import annotations

import pytest
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


def test_native_agent_turn_returns_core_rendered_copy_without_outbox(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = _turn(client, "Hola, quiero pedir una cita")

    assert response.status_code == 200
    body = response.json()
    assert body["reply_key"] == "vedruna_ask_clinic"
    assert body["copy_text"] == (
        "Claro. Para que clinica quieres la cita: Madre Vedruna o Santa Isabel?"
    )
    assert body["next_step"] == "collect_missing_booking_field"
    assert body["pending_fields"] == ["clinic"]
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


@pytest.mark.parametrize(
    "utterance",
    ["A las dieciseis veinte", "La dos", "Opcion dos"],
)
def test_native_agent_resolves_natural_spoken_slot_selection(
    monkeypatch,
    utterance: str,
) -> None:
    client = _client(monkeypatch)
    conversation_id = f"native-slot-{utterance}"
    for turn in [
        "Quiero cita en Santa Isabel para una ecografia",
        "Me llamo Ana Perez",
        "600111222",
        "Tengo dolor en el talon",
        "Miercoles por la tarde",
    ]:
        response = _turn(client, turn, conversation_id=conversation_id)
        assert response.status_code == 200

    selected = _turn(client, utterance, conversation_id=conversation_id)
    body = selected.json()

    assert body["requires_explicit_confirmation"] is True
    assert body["next_step"] == "request_explicit_confirmation"
    state = get_state_manager().load(
        f"elevenlabs-native:{conversation_id}",
        "vedruna",
    )
    assert state.slots["selected_slot_time"] == "16:20"


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


def test_native_agent_keeps_booking_state_across_all_required_fields(monkeypatch) -> None:
    client = _client(monkeypatch)
    conversation_id = "native-stateful-booking"

    steps = [
        ("Quiero coger una cita", "vedruna_ask_clinic"),
        ("Santa Isabel", "vedruna_ask_service_santa"),
        ("Infiltracion", "vedruna_ask_first_name"),
        ("Pau", "vedruna_ask_last_names"),
        ("Marco Marti", "vedruna_ask_phone"),
        ("645290441", "vedruna_ask_reason"),
        ("Dolor en el talon", "vedruna_ask_date"),
    ]

    for index, (utterance, expected_reply_key) in enumerate(steps):
        response = _turn(client, utterance, conversation_id=conversation_id)
        assert response.status_code == 200
        body = response.json()
        assert body["reply_key"] == expected_reply_key
        if index:
            assert body["clinic"] == "santa_isabel"
        assert body["copy_text"]

    state = get_state_manager().load(
        "elevenlabs-native:native-stateful-booking",
        "vedruna",
    )
    assert state.slots["clinic"] == "santa_isabel"
    assert state.slots["service"] == "infiltracion"
    assert state.slots["patient_phone"] == "645290441"
