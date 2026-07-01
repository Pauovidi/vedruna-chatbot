from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

import core.conversation.orchestrator as orchestrator_module
from core.config import Settings
from core.conversation.contracts import NormalizedInbound
from core.conversation.copy_renderer import RenderedReply, render_conversation_reply
from core.conversation.orchestrator import ConversationOrchestrator
from core.conversation.policy import decide_next_action
from core.conversation.runtime import ConversationRuntimeAdapters, run_conversation_turn
from core.conversation.state_manager import ConversationState, StateManager
from core.conversation.state_reducer import reduce_conversation_state
from core.knowledge.retriever import SimpleKnowledgeRetriever
from core.llm.openai_provider import OpenAIProvider
from core.llm.schemas import IncomingMessage
from core.nlu.deterministic_interpreter import DeterministicNLUInterpreter
from core.nlu.schemas import NLUResult
from core.observability.events import EventRecorder
from core.outbox import MemoryOutbox
from core.persistence.memory import MemoryStore
from core.tools.check_conversation_authority import check_conversation_authority
from core.tools.registry import ToolRegistry


class FailingNLUProvider(OpenAIProvider):
    def interpret(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("nlu unavailable")


class TextLeakingProvider(OpenAIProvider):
    def interpret(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return NLUResult(
            intent="general",
            raw_provider_info_sanitized={"output_text": "DO NOT SHOW THIS"},
        )


class TimeoutNLUProvider(OpenAIProvider):
    def interpret(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise TimeoutError("provider timed out")


def test_nlu_returns_structure_not_visible_reply() -> None:
    result = DeterministicNLUInterpreter().interpret(
        IncomingMessage(conversation_id="nlu-1", text="solo informacion"),
        {},
        [],
        [],
    )
    assert isinstance(result, NLUResult)
    assert not hasattr(result, "reply_text")
    assert result.is_information_only is True


def test_nlu_result_forbids_visible_reply_fields() -> None:
    with pytest.raises(ValidationError):
        NLUResult(intent="general", reply_text="visible bypass")  # type: ignore[call-arg]


def test_state_reducer_cancels_flow_for_information_only() -> None:
    state = ConversationState(
        conversation_id="state-1",
        current_flow="appointment",
        active_topic="appointment",
    )
    nlu = NLUResult(intent="information_only", is_information_only=True)
    updated = reduce_conversation_state(
        state,
        nlu,
        IncomingMessage(conversation_id="state-1", text="solo informacion"),
        None,
    )
    assert updated.current_flow is None
    assert updated.information_only is True


def test_state_reducer_correction_wins_over_previous_context() -> None:
    state = ConversationState(conversation_id="state-2", collected_info={"missing_items": 1})
    nlu = NLUResult(
        intent="correction",
        entities={"missing_items": 8},
        signals=["correction"],
    )
    updated = reduce_conversation_state(
        state,
        nlu,
        IncomingMessage(conversation_id="state-2", text="me faltan 8, no una"),
        None,
    )
    assert updated.collected_info["missing_items"] == 8


def test_policy_action_drives_copy_renderer() -> None:
    state = ConversationState(conversation_id="policy-1", client_id="mudanzas_example")
    nlu = NLUResult(intent="quote_lead", active_topic_hint="quote_lead")
    action = decide_next_action(state, nlu)
    rendered = render_conversation_reply(action, state, "whatsapp")
    assert action.action_type == "ask_missing_context"
    assert action.reply_key == "mudanzas_ask_origin"
    assert rendered.reply_key == action.reply_key
    assert "origen" in rendered.text.lower()


def test_openai_provider_legacy_decide_is_disabled() -> None:
    provider = OpenAIProvider(Settings(OPENAI_API_KEY="", DATABASE_URL=""))
    with pytest.raises(RuntimeError, match="Legacy decide"):
        provider.decide()


def test_no_legacy_conversation_decision_schema_in_core_runtime() -> None:
    root = Path(__file__).resolve().parents[1]
    core_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (root / "core").rglob("*.py")
        if "__pycache__" not in path.parts
    )
    assert "ConversationDecision" not in core_text
    assert ".decide(" not in core_text


def test_orchestrator_uses_rendered_reply_as_final_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def fake_renderer(action, context, channel, tool_results=None):  # type: ignore[no-untyped-def]
        calls.append((action.reply_key, channel, tool_results))
        return RenderedReply(
            text=f"rendered::{action.reply_key}",
            channel=channel,
            reply_key=action.reply_key,
        )

    monkeypatch.setattr(orchestrator_module, "render_conversation_reply", fake_renderer)
    settings = Settings(
        OPENAI_API_KEY="",
        CONVERSATIONAL_REPLY_ENABLED=False,
        DATABASE_URL="",
    )
    store = MemoryStore()
    result = ConversationOrchestrator(
        OpenAIProvider(settings),
        StateManager(store),
        SimpleKnowledgeRetriever(),
        ToolRegistry(),
        EventRecorder(store),
        settings=settings,
    ).handle_turn(IncomingMessage(conversation_id="render-1", text="hola"))

    assert calls
    assert result.reply_text == f"rendered::{result.reply_key}"
    assert result.action_type is not None
    assert result.reply_key is not None


def test_nlu_failure_fallback_still_uses_policy_and_copy() -> None:
    settings = Settings(
        OPENAI_API_KEY="sk-test",
        CONVERSATIONAL_REPLY_ENABLED=True,
        CONVERSATIONAL_REPLY_SHADOW=False,
        DATABASE_URL="",
    )
    store = MemoryStore()
    result = ConversationOrchestrator(
        FailingNLUProvider(settings),
        StateManager(store),
        SimpleKnowledgeRetriever(),
        ToolRegistry(),
        EventRecorder(store),
        settings=settings,
    ).handle_turn(IncomingMessage(conversation_id="nlu-fallback-1", text="hola"))

    event_types = [event.type for event in store.list_events("nlu-fallback-1")]
    assert "llm_interpretation_failed" in event_types
    assert "policy_action" in event_types
    assert "rendered_reply" in event_types
    assert result.action_type == "fallback_contextual"
    assert result.reply_key == "fallback_contextual"


def test_openai_timeout_fallback_records_timing_event() -> None:
    settings = Settings(
        OPENAI_API_KEY="sk-test",
        CONVERSATIONAL_REPLY_ENABLED=True,
        CONVERSATIONAL_REPLY_SHADOW=False,
        DATABASE_URL="",
    )
    store = MemoryStore()
    result = ConversationOrchestrator(
        TimeoutNLUProvider(settings),
        StateManager(store),
        SimpleKnowledgeRetriever(),
        ToolRegistry(),
        EventRecorder(store),
        settings=settings,
    ).handle_turn(IncomingMessage(conversation_id="timeout-1", text="hola"))
    event_types = [event.type for event in store.list_events("timeout-1")]
    timing = [
        event.payload
        for event in store.list_events("timeout-1")
        if event.type == "authority_turn_timing_completed"
    ][-1]
    assert "nlu_provider_timeout_fallback_used" in event_types
    assert timing["timedOutStage"] == "openai_responses"
    assert timing["usedFallback"] is True
    assert result.reply_text


def test_provider_output_text_is_ignored_by_policy_runtime() -> None:
    settings = Settings(
        OPENAI_API_KEY="sk-test",
        CONVERSATIONAL_REPLY_ENABLED=True,
        CONVERSATIONAL_REPLY_SHADOW=False,
        DATABASE_URL="",
    )
    store = MemoryStore()
    result = ConversationOrchestrator(
        TextLeakingProvider(settings),
        StateManager(store),
        SimpleKnowledgeRetriever(),
        ToolRegistry(),
        EventRecorder(store),
        settings=settings,
    ).handle_turn(IncomingMessage(conversation_id="leak-1", text="hola"))
    assert "DO NOT SHOW THIS" not in result.reply_text
    assert result.reply_key == "fallback_contextual"


def test_authority_trace_and_state_after_timing_are_emitted() -> None:
    settings = Settings(
        OPENAI_API_KEY="",
        CONVERSATIONAL_REPLY_ENABLED=False,
        DATABASE_URL="",
    )
    store = MemoryStore()
    result = ConversationOrchestrator(
        OpenAIProvider(settings),
        StateManager(store),
        SimpleKnowledgeRetriever(),
        ToolRegistry(),
        EventRecorder(store),
        settings=settings,
    ).handle_turn(IncomingMessage(conversation_id="trace-1", text="cuanto cuesta?"))

    events = store.list_events("trace-1")
    event_types = [event.type for event in events]
    trace = [event.payload for event in events if event.type == "authority_turn_completed"][-1]
    timing = [
        event.payload
        for event in events
        if event.type == "authority_turn_timing_completed"
    ][-1]
    assert "state_after_invariants" in event_types
    assert "authority_turn_timing_completed" in event_types
    assert trace["nluProviderUsed"] == "deterministic"
    assert trace["policyAction"] == result.action_type
    assert trace["renderKey"] == result.reply_key
    assert timing["openaiCalls"] == 0
    assert timing["totalDurationMs"] >= 0
    assert result.authority_trace is not None


def test_human_mode_allows_explicit_return_to_bot_command() -> None:
    settings = Settings(
        OPENAI_API_KEY="",
        CONVERSATIONAL_REPLY_ENABLED=False,
        DATABASE_URL="",
    )
    store = MemoryStore()
    orchestrator = ConversationOrchestrator(
        OpenAIProvider(settings),
        StateManager(store),
        SimpleKnowledgeRetriever(),
        ToolRegistry(),
        EventRecorder(store),
        settings=settings,
    )
    state = orchestrator.state_manager.load("human-return-1", "default")
    state.mode = "human"
    orchestrator.state_manager.save(state)

    result = orchestrator.handle_turn(
        IncomingMessage(conversation_id="human-return-1", text="volver al bot")
    )
    event_types = [event.type for event in store.list_events("human-return-1")]
    assert "human_mode_returned_to_bot" in event_types
    assert result.mode == "bot"
    assert result.reply_text


def test_runtime_facade_and_outbox_are_used() -> None:
    settings = Settings(
        OPENAI_API_KEY="",
        CONVERSATIONAL_REPLY_ENABLED=False,
        DATABASE_URL="",
    )
    store = MemoryStore()
    outbox = MemoryOutbox()
    orchestrator = ConversationOrchestrator(
        OpenAIProvider(settings),
        StateManager(store),
        SimpleKnowledgeRetriever(),
        ToolRegistry(),
        EventRecorder(store),
        settings=settings,
        outbox=outbox,
    )
    result = run_conversation_turn(
        NormalizedInbound(
            conversationId="runtime-1",
            clientId="default",
            text="hola",
            channel="whatsapp",
        ),
        ConversationRuntimeAdapters(orchestrator=orchestrator),
    )
    assert result.reply_text
    assert outbox.messages[0].reply_key == result.reply_key
    assert any(event.type == "outbox_sent" for event in store.list_events("runtime-1"))


def test_authority_checker_passes_current_repo() -> None:
    assert check_conversation_authority() == []
