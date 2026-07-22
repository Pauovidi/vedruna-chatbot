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
from core.adapters.vedruna.channels.elevenlabs_custom_llm import completion_events
from core.config import get_settings
from core.llm.openai_provider import OpenAIProvider
from core.llm.schemas import ChatTurnResult, ToolResult
from core.nlu.deterministic_interpreter import DeterministicNLUInterpreter


def _reset_dependencies() -> None:
    get_orchestrator.cache_clear()
    get_state_manager.cache_clear()
    get_events.cache_clear()
    get_store.cache_clear()
    get_registry.cache_clear()
    get_retriever.cache_clear()
    get_settings.cache_clear()


def _client(
    monkeypatch,
    *,
    openai_api_key: str = "",
    remote_nlu_enabled: bool = False,
) -> TestClient:
    monkeypatch.setenv("ELEVENLABS_CUSTOM_LLM_API_KEY", "test-custom-llm-key")
    monkeypatch.setenv("OPENAI_API_KEY", openai_api_key)
    monkeypatch.setenv(
        "ELEVENLABS_REMOTE_NLU_ENABLED",
        str(remote_nlu_enabled).lower(),
    )
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


def test_custom_llm_treats_anonymous_messages_as_safe_connection_probes(monkeypatch) -> None:
    client = _client(monkeypatch)
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test-custom-llm-key"},
        json={"messages": [{"role": "user", "content": "hola"}]},
    )
    assert response.status_code == 200
    assert "Clinica Madre Vedruna" not in response.text
    assert response.text.endswith("data: [DONE]\n\n")


def test_custom_llm_accepts_openai_standard_user_identifier(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test-custom-llm-key"},
        json={
            "model": "vedruna-core",
            "user": "eleven-preview-user",
            "messages": [{"role": "user", "content": "quiero una cita"}],
        },
    )

    assert response.status_code == 200
    assert "chat.completion.chunk" in response.text


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
    assert "logprobs" not in first_choice
    assert "system_fingerprint" not in events[0]
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


def test_custom_llm_ignores_requests_without_a_current_user_message(monkeypatch) -> None:
    client = _client(monkeypatch)
    response = client.post(
        "/v1/chat/completions",
        headers={
            "Authorization": "Bearer test-custom-llm-key",
            "X-ElevenLabs-Conversation-ID": "conv-empty-message",
        },
        json={
            "model": "vedruna-core",
            "messages": [{"role": "assistant", "content": "Bienvenida"}],
            "stream": True,
        },
    )

    assert response.status_code == 200
    assert "Un momento" not in response.text
    assert "Para que clinica" not in response.text


def test_custom_llm_accepts_a_stateless_elevenlabs_connection_check(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test-custom-llm-key"},
        json={"model": "vedruna-core", "messages": [], "stream": True},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "Un momento, por favor" in response.text
    assert response.text.endswith("data: [DONE]\n\n")


def test_custom_llm_uses_structured_nlu_without_remote_round_trip(monkeypatch) -> None:
    def remote_nlu_must_not_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("ElevenLabs custom LLM must not invoke remote NLU")

    monkeypatch.setattr(OpenAIProvider, "interpret", remote_nlu_must_not_run)
    client = _client(monkeypatch, openai_api_key="sk-test")

    response = _request(client, text="Hola, quiero pedir una cita")

    assert response.status_code == 200
    assert "Madre Vedruna" in response.text
    assert "Santa Isabel" in response.text


def test_custom_llm_can_use_remote_structured_nlu_when_enabled(monkeypatch) -> None:
    calls: list[str] = []
    deterministic = DeterministicNLUInterpreter()

    def remote_nlu(self, message, context, snippets, tools):  # type: ignore[no-untyped-def]
        del self
        calls.append(message.text)
        return deterministic.interpret(message, context, snippets, tools)

    monkeypatch.setattr(OpenAIProvider, "interpret", remote_nlu)
    client = _client(
        monkeypatch,
        openai_api_key="sk-test",
        remote_nlu_enabled=True,
    )

    response = _request(client, text="Hola, quiero pedir una cita")

    assert response.status_code == 200
    assert calls == ["Hola, quiero pedir una cita"]
    assert "Madre Vedruna" in response.text


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
    assert "Es para una cita de podologia" in first.text

    response = _request(
        client,
        text="Si, y tengo Sanitas",
        conversation_id=conversation_id,
    )

    assert response.status_code == 200
    assert "Para continuar, dime tu nombre" in response.text


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


def test_custom_llm_understands_natural_patient_name_and_last_names(monkeypatch) -> None:
    client = _client(monkeypatch)
    conversation_id = "conv-natural-patient-name"

    for text in [
        "Quiero una cita en Madre Vedruna",
        "Si",
        "Sanitas",
    ]:
        _request(client, text=text, conversation_id=conversation_id)

    first_name = _request(
        client,
        text="Mi nombre es Prueba",
        conversation_id=conversation_id,
    )
    assert "apellidos" in first_name.text.lower()

    last_names = _request(
        client,
        text="Mis apellidos son De Ejemplo",
        conversation_id=conversation_id,
    )
    assert "telefono" in last_names.text.lower()


def test_custom_llm_accepts_bare_answers_for_prompted_patient_fields(monkeypatch) -> None:
    client = _client(monkeypatch)
    conversation_id = "conv-bare-patient-fields"

    first = _request(
        client,
        text="Quiero una cita en Madre Vedruna para podologia y tengo Sanitas",
        conversation_id=conversation_id,
    )
    assert "nombre" in first.text.lower()

    last_names = _request(client, text="Laura", conversation_id=conversation_id)
    assert "apellidos" in last_names.text.lower()

    phone = _request(client, text="Garcia Perez", conversation_id=conversation_id)
    assert "telefono" in phone.text.lower()

    reason = _request(client, text="600111222", conversation_id=conversation_id)
    assert "motivo" in reason.text.lower()

    date = _request(
        client,
        text="revision preventiva",
        conversation_id=conversation_id,
    )
    assert "dia" in date.text.lower()


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
    assert "confirmes claramente" in response.text.lower()


def test_custom_llm_suppresses_elevenlabs_transfer_when_disabled(monkeypatch) -> None:
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
    assert all("tool_calls" not in event["choices"][0]["delta"] for event in events)
    assert "transferencia real" in response.text.lower()


def test_completion_events_emits_transfer_only_after_real_transfer() -> None:
    result = ChatTurnResult(
        conversation_id="conv-transfer",
        intent="price_query",
        reply_key="vedruna_voice_transfer",
        reply_text="Te paso con la clinica.",
        tool_results=[
            ToolResult(
                name="voice_transfer_call",
                status="success",
                user_safe_summary="Transferencia simulada completada.",
                data={
                    "transfer_enabled": True,
                    "real_transfer_executed": True,
                    "arguments": {"clinic": "santa_isabel"},
                },
            )
        ],
    )
    stream = "".join(
        completion_events(
            lambda: result,
            model="vedruna-core",
            available_tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "transfer_to_number",
                        "parameters": {"type": "object"},
                    },
                }
            ],
            emit_initial_buffer=False,
        )
    )
    events = [
        json.loads(line.removeprefix("data: "))
        for line in stream.splitlines()
        if line.startswith("data: {")
    ]

    tool_calls = events[0]["choices"][0]["delta"]["tool_calls"]
    function = tool_calls[0]["function"]
    assert function["name"] == "transfer_to_number"
    arguments = json.loads(function["arguments"])
    assert arguments["transfer_number"] == "+34976582768"
