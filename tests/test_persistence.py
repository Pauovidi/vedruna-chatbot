from __future__ import annotations

from pathlib import Path

import pytest

import core.conversation.copy_renderer as copy_renderer_module
from core.config import Settings
from core.conversation.actions import ConversationAction
from core.conversation.copy_renderer import render_conversation_reply
from core.conversation.orchestrator import ConversationOrchestrator
from core.conversation.state_manager import StateManager
from core.knowledge.retriever import SimpleKnowledgeRetriever
from core.llm.openai_provider import OpenAIProvider
from core.llm.schemas import IncomingMessage, ToolCallRequest, ToolResult
from core.observability.events import EventRecorder
from core.persistence.factory import build_conversation_store
from core.persistence.sqlalchemy_store import SQLAlchemyConversationStore
from core.tools.executor import ToolExecutor
from core.tools.registry import ToolRegistry
from core.tools.schemas import ToolHandler


class FailingInterpreter(OpenAIProvider):
    def interpret(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("llm failed")


class FailingToolHandler(ToolHandler):
    def execute(
        self,
        request: ToolCallRequest,
        context: dict[str, object],
    ) -> ToolResult:
        del request, context
        raise RuntimeError("tool failed")


def test_memory_store_in_development_without_database_url() -> None:
    store = build_conversation_store(Settings(APP_ENV="development", DATABASE_URL=""))
    assert store.store_type == "memory"
    assert store.ephemeral_store is True


def test_sqlite_persists_state_messages_and_events_between_instances(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'core.db'}"
    first = SQLAlchemyConversationStore(database_url)
    state = first.load_state("persist-1", "default")
    state.active_topic = "quote_lead"
    first.save_state(state)
    first.append_message("persist-1", "user", "hola", client_id="default")
    first.record_events(
        [
            ("persist-1", "example", {"api_key": "secret"}),
            ("persist-1", "example_follow_up", {}),
        ]
    )

    second = SQLAlchemyConversationStore(database_url)
    loaded = second.load_state("persist-1", "default")
    assert loaded.active_topic == "quote_lead"
    assert second.list_messages("persist-1")[0]["text"] == "hola"
    events = second.list_events("persist-1")
    assert events[0].payload["api_key"] == "[redacted]"
    assert [event.type for event in events] == ["example", "example_follow_up"]


def test_inbound_persists_when_llm_fails() -> None:
    settings = Settings(
        OPENAI_API_KEY="sk-test",
        CONVERSATIONAL_REPLY_ENABLED=True,
        CONVERSATIONAL_REPLY_SHADOW=False,
        DATABASE_URL="",
    )
    store = build_conversation_store(settings)
    orchestrator = ConversationOrchestrator(
        FailingInterpreter(settings),
        StateManager(store),
        SimpleKnowledgeRetriever(),
        ToolRegistry(),
        EventRecorder(store),
        settings=settings,
    )
    result = orchestrator.handle_turn(
        IncomingMessage(conversation_id="llm-fail-1", text="hola")
    )
    messages = store.list_messages("llm-fail-1")
    assert messages[0]["role"] == "user"
    assert result.reply_text
    assert any(
        event.type == "llm_interpretation_failed"
        for event in store.list_events("llm-fail-1")
    )


def test_inbound_persists_when_tool_fails() -> None:
    settings = Settings(
        OPENAI_API_KEY="",
        CONVERSATIONAL_REPLY_ENABLED=False,
        DATABASE_URL="",
    )
    store = build_conversation_store(settings)
    registry = ToolRegistry()
    events = EventRecorder(store)
    orchestrator = ConversationOrchestrator(
        OpenAIProvider(settings),
        StateManager(store),
        SimpleKnowledgeRetriever(),
        registry,
        events,
        settings=settings,
    )
    orchestrator.executor = ToolExecutor(
        registry,
        events,
        handlers={"stub": FailingToolHandler()},
    )
    result = orchestrator.handle_turn(
        IncomingMessage(
            conversation_id="tool-fail-1",
            text="Estoy enfadado, nadie me contesta",
            channel="whatsapp",
        )
    )
    messages = store.list_messages("tool-fail-1")
    assert messages[0]["role"] == "user"
    assert messages[0]["text"] == "Estoy enfadado, nadie me contesta"
    assert result.reply_key == "tool_failed_visible"
    assert any(event.type == "tool_failed" for event in store.list_events("tool-fail-1"))


def test_sanitizer_copy_change_does_not_mutate_inbound_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = build_conversation_store(Settings(DATABASE_URL=""))
    store.append_message("sanitize-1", "user", "texto original con intent")
    monkeypatch.setitem(
        copy_renderer_module.COPY_BY_KEY,
        "bad_internal_copy",
        "This mentions policy and NLU.",
    )
    rendered = render_conversation_reply(
        ConversationAction(
            action_type="fallback_contextual",
            reply_intent="bad_copy",
            reply_key="bad_internal_copy",
            metadata={"forces_fallback_copy": True},
        ),
        StateManager(store).load("sanitize-1", "default"),
        "whatsapp",
    )
    assert rendered.text
    assert "policy" not in rendered.text.lower()
    assert "nlu" not in rendered.text.lower()
    assert store.list_messages("sanitize-1")[0]["text"] == "texto original con intent"
