from __future__ import annotations

import json

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
    monkeypatch.setenv("ELEVENLABS_CUSTOM_LLM_API_KEY", "test-custom-llm-key")
    monkeypatch.setenv("OPENAI_API_KEY", "")
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
    assert events[0]["choices"][0]["delta"] == {"role": "assistant"}
    assert events[1]["choices"][0]["delta"]["content"]
    assert events[-1]["choices"][0]["finish_reason"] == "stop"


def test_custom_llm_greeting_with_booking_request_starts_booking(monkeypatch) -> None:
    client = _client(monkeypatch)
    response = _request(client, text="Hola, quiero pedir una cita")
    assert response.status_code == 200
    assert "Madre Vedruna" in response.text
    assert "Santa Isabel" in response.text


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
    tool_calls = events[0]["choices"][0]["delta"]["tool_calls"]
    function = tool_calls[0]["function"]
    assert function["name"] == "transfer_to_number"
    arguments = json.loads(function["arguments"])
    assert arguments["transfer_number"] == "+34976582768"
    assert "precio" not in response.text.lower()
