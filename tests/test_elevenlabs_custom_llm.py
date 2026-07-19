from __future__ import annotations

import json
from threading import Event

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
from core.adapters.vedruna.channels.elevenlabs_custom_llm import completion_events
from core.config import get_settings
from core.llm.openai_provider import OpenAIProvider
from core.llm.schemas import ChatTurnResult


def _reset_dependencies() -> None:
    get_orchestrator.cache_clear()
    get_state_manager.cache_clear()
    get_events.cache_clear()
    get_store.cache_clear()
    get_registry.cache_clear()
    get_retriever.cache_clear()
    get_settings.cache_clear()


def _client(monkeypatch, *, openai_api_key: str = "") -> TestClient:
    monkeypatch.setenv("ELEVENLABS_CUSTOM_LLM_API_KEY", "test-custom-llm-key")
    monkeypatch.setenv("OPENAI_API_KEY", openai_api_key)
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("RPA_DRY_RUN", "true")
    monkeypatch.setenv("VOICE_TRANSFER_ENABLED", "false")
    _reset_dependencies()
    return TestClient(app)


def _request(
    client: TestClient,
    *,
    text: str,
    conversation_id: str = "conv-test",
    tools: list[dict[str, object]] | None = None,
):
    return client.post(
        "/v1/chat/completions",
        headers={
            "Authorization": "Bearer test-custom-llm-key",
            "X-ElevenLabs-Conversation-ID": conversation_id,
        },
        json={
            "model": "vedruna-core",
            "messages": [{"role": "user", "content": text}],
            "stream": True,
            "tools": tools or [],
        },
    )


def _events(response) -> list[dict[str, object]]:
    events = []
    for line in response.text.splitlines():
        if not line.startswith("data: {"):
            continue
        events.append(json.loads(line.removeprefix("data: ")))
    return events


def test_custom_llm_requires_auth(monkeypatch) -> None:
    client = _client(monkeypatch)
    response = client.post(
        "/v1/chat/completions",
        headers={"X-ElevenLabs-Conversation-ID": "conv-auth"},
        json={"messages": [{"role": "user", "content": "hola"}]},
    )
    assert response.status_code == 401


def test_custom_llm_requires_stable_conversation_id(monkeypatch) -> None:
    client = _client(monkeypatch)
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test-custom-llm-key"},
        json={"messages": [{"role": "user", "content": "hola"}]},
    )
    assert response.status_code == 400


def test_custom_llm_streams_renderer_copy(monkeypatch) -> None:
    client = _client(monkeypatch)
    response = _request(client, text="hola")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "Clinica Madre Vedruna" in response.text
    assert response.text.endswith("data: [DONE]\n\n")
    events = _events(response)
    first_choice = events[0]["choices"][0]
    assert first_choice["delta"]["role"] == "assistant"
    assert first_choice["delta"]["content"].endswith("... ")
    assert first_choice["logprobs"] is None
    assert events[0]["system_fingerprint"] is None
    assert events[1]["choices"][0]["delta"]["content"]
    assert events[-1]["choices"][0]["finish_reason"] == "stop"


def test_custom_llm_streams_before_running_core() -> None:
    calls: list[str] = []

    def build_result() -> ChatTurnResult:
        calls.append("run")
        return ChatTurnResult(conversation_id="conv-latency", reply_text="hola")

    events = completion_events(
        build_result,
        model="vedruna-core",
        available_tools=[],
    )
    first_event = next(events)
    assert '"role": "assistant"' in first_event
    assert '"content": "Un momento, por favor... "' in first_event
    assert calls == []
    next(events)
    assert calls == ["run"]


def test_custom_llm_sends_sse_heartbeats_while_core_is_running() -> None:
    release_result = Event()

    def build_result() -> ChatTurnResult:
        release_result.wait()
        return ChatTurnResult(conversation_id="conv-heartbeat", reply_text="hola")

    events = completion_events(
        build_result,
        model="vedruna-core",
        available_tools=[],
        heartbeat_interval_seconds=0.001,
    )

    first_event = next(events)
    assert '"content": "Un momento, por favor... "' in first_event
    assert next(events) == ": keep-alive\n\n"
    release_result.set()
    assert '"content": "hola"' in next(events)


def test_custom_llm_uses_structured_nlu_without_remote_round_trip(monkeypatch) -> None:
    def remote_nlu_must_not_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("ElevenLabs custom LLM must not invoke remote NLU")

    monkeypatch.setattr(OpenAIProvider, "interpret", remote_nlu_must_not_run)
    client = _client(monkeypatch, openai_api_key="sk-test")

    response = _request(client, text="Hola, quiero pedir una cita")

    assert response.status_code == 200
    assert "Madre Vedruna" in response.text
    assert "Santa Isabel" in response.text


def test_custom_llm_greeting_with_booking_request_starts_booking(monkeypatch) -> None:
    client = _client(monkeypatch)
    response = _request(client, text="Hola, quiero pedir una cita")
    assert response.status_code == 200
    assert "Madre Vedruna" in response.text
    assert "Santa Isabel" in response.text


def test_custom_llm_understands_madre_vedruna_service_confirmation(monkeypatch) -> None:
    client = _client(monkeypatch)
    conversation_id = "conv-madre-confirmation"

    first = _request(
        client,
        text="Quiero una cita en Madre Vedruna",
        conversation_id=conversation_id,
    )
    assert "Es para podologia" in first.text

    response = _request(
        client,
        text="Si, y tengo Sanitas",
        conversation_id=conversation_id,
    )

    assert response.status_code == 200
    assert "Dime tu nombre" in response.text


def test_custom_llm_understands_natural_service_confirmation(monkeypatch) -> None:
    client = _client(monkeypatch)
    conversation_id = "conv-madre-natural-confirmation"

    _request(
        client,
        text="Quiero una cita en Madre Vedruna",
        conversation_id=conversation_id,
    )
    response = _request(
        client,
        text="Asi es",
        conversation_id=conversation_id,
    )

    assert response.status_code == 200
    assert "Sanitas" in response.text
    assert "Es para podologia" not in response.text


def test_custom_llm_santa_isabel_insurance_is_particular_only(monkeypatch) -> None:
    client = _client(monkeypatch)
    response = _request(
        client,
        text="Quiero cita en Santa Isabel y tengo Sanitas",
        conversation_id="conv-santa-insurance",
    )
    assert response.status_code == 200
    assert "particular" in response.text.lower()
    assert "que necesitas" not in response.text.lower()


def test_custom_llm_preserves_state_and_dry_run_blocks_real_booking(monkeypatch) -> None:
    client = _client(monkeypatch)
    conversation_id = "conv-booking"
    turns = [
        "quiero cita en Santa Isabel para quiropodia",
        "me llamo Ana Perez",
        "600111222",
        "dolor en un callo",
        "miercoles por la tarde",
        "la primera",
    ]
    response = None
    for text in turns:
        response = _request(client, text=text, conversation_id=conversation_id)
        assert response.status_code == 200
    assert response is not None
    assert "Confirmamos tu cita" not in response.text
    assert "prueba" in response.text.lower() or "real" in response.text.lower()


def test_custom_llm_emits_elevenlabs_transfer_tool_call(monkeypatch) -> None:
    client = _client(monkeypatch)
    response = _request(
        client,
        text="quiero saber el precio en Santa Isabel",
        conversation_id="conv-transfer",
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "transfer_to_number",
                    "parameters": {"type": "object"},
                },
            }
        ],
    )
    assert response.status_code == 200
    events = _events(response)
    tool_calls = events[1]["choices"][0]["delta"]["tool_calls"]
    function = tool_calls[0]["function"]
    assert function["name"] == "transfer_to_number"
    arguments = json.loads(function["arguments"])
    assert arguments["transfer_number"] == "+34976582768"
    assert "precio" not in response.text.lower()
