from __future__ import annotations

from functools import lru_cache

from core.adapters.vedruna.tools import get_vedruna_tool_handlers
from core.clients import load_client_tools
from core.config import ROOT_DIR, get_settings
from core.conversation.orchestrator import ConversationOrchestrator
from core.conversation.state_manager import StateManager
from core.knowledge.json_seed_loader import load_seed
from core.knowledge.retriever import SimpleKnowledgeRetriever
from core.llm.openai_provider import OpenAIProvider
from core.observability.events import EventRecorder
from core.persistence.factory import build_conversation_store
from core.tools.registry import ToolRegistry


@lru_cache
def get_store():
    return build_conversation_store(get_settings())


@lru_cache
def get_events() -> EventRecorder:
    return EventRecorder(get_store())


@lru_cache
def get_state_manager() -> StateManager:
    return StateManager(get_store())


@lru_cache
def get_retriever() -> SimpleKnowledgeRetriever:
    retriever = SimpleKnowledgeRetriever()
    clients_dir = ROOT_DIR / "clients"
    for seed in clients_dir.glob("*/knowledge_seed.json"):
        retriever.add_entries(load_seed(seed, seed.parent.name))
    return retriever


@lru_cache
def get_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.extend(load_client_tools())
    return registry


@lru_cache
def get_orchestrator() -> ConversationOrchestrator:
    settings = get_settings()
    return ConversationOrchestrator(
        llm=OpenAIProvider(settings),
        state_manager=get_state_manager(),
        retriever=get_retriever(),
        registry=get_registry(),
        events=get_events(),
        settings=settings,
        tool_handlers=get_vedruna_tool_handlers(settings),
    )
