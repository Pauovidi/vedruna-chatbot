from __future__ import annotations

from core.config import Settings
from core.conversation.orchestrator import ConversationOrchestrator
from core.conversation.state_manager import StateManager
from core.knowledge.retriever import SimpleKnowledgeRetriever
from core.llm.openai_provider import OpenAIProvider
from core.llm.schemas import IncomingMessage
from core.observability.events import EventRecorder
from core.persistence.memory import MemoryStore
from core.prompts.loader import PromptLoader
from core.tools.registry import ToolRegistry


class CountingProvider(OpenAIProvider):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.calls = 0

    def interpret(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        return super().interpret(*args, **kwargs)


def test_prompt_loader_loads_base_channel_client_and_policies() -> None:
    bundle = PromptLoader().load("mudanzas_example", "whatsapp")
    text = bundle.system_text()
    assert "Base Agent" in text
    assert "WhatsApp" in text
    assert "Safety Policy" in text
    assert "Privacy Policy" in text
    assert "Tool Policy" in text


def test_disabled_llm_flag_does_not_call_openai() -> None:
    settings = Settings(
        OPENAI_API_KEY="sk-test",
        CONVERSATIONAL_REPLY_ENABLED=False,
        CONVERSATIONAL_REPLY_SHADOW=False,
        DATABASE_URL="",
    )
    provider = CountingProvider(settings)
    store = MemoryStore()
    orchestrator = ConversationOrchestrator(
        provider,
        StateManager(store),
        SimpleKnowledgeRetriever(),
        ToolRegistry(),
        EventRecorder(store),
        settings=settings,
    )
    orchestrator.handle_turn(IncomingMessage(conversation_id="flags-1", text="hola"))
    assert provider.calls == 0
    assert any(event.type == "llm_disabled" for event in store.list_events("flags-1"))


def test_shadow_mode_does_not_call_openai_by_default() -> None:
    settings = Settings(
        OPENAI_API_KEY="sk-test",
        CONVERSATIONAL_REPLY_ENABLED=True,
        CONVERSATIONAL_REPLY_SHADOW=True,
        CONVERSATIONAL_REPLY_SHADOW_CALL_ENABLED=False,
        DATABASE_URL="",
    )
    provider = CountingProvider(settings)
    store = MemoryStore()
    orchestrator = ConversationOrchestrator(
        provider,
        StateManager(store),
        SimpleKnowledgeRetriever(),
        ToolRegistry(),
        EventRecorder(store),
        settings=settings,
    )
    orchestrator.handle_turn(IncomingMessage(conversation_id="flags-2", text="hola"))
    assert provider.calls == 0
    assert any(
        event.type == "llm_shadow_primary_deterministic"
        for event in store.list_events("flags-2")
    )
