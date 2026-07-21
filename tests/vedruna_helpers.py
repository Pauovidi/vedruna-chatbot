from __future__ import annotations

from core.adapters.vedruna.tools import get_vedruna_tool_handlers
from core.clients import load_client_tools
from core.config import Settings
from core.conversation.orchestrator import ConversationOrchestrator
from core.conversation.state_manager import StateManager
from core.knowledge.retriever import SimpleKnowledgeRetriever
from core.llm.openai_provider import OpenAIProvider
from core.llm.schemas import IncomingMessage
from core.observability.events import EventRecorder
from core.persistence.memory import MemoryStore
from core.tools.registry import ToolRegistry


def make_vedruna_orchestrator() -> tuple[ConversationOrchestrator, MemoryStore]:
    settings = Settings(
        OPENAI_API_KEY="",
        CONVERSATIONAL_REPLY_ENABLED=False,
        CONVERSATIONAL_REPLY_SHADOW=False,
        DATABASE_URL="",
        RPA_DRY_RUN=True,
    )
    store = MemoryStore()
    registry = ToolRegistry()
    registry.extend(load_client_tools())
    orchestrator = ConversationOrchestrator(
        OpenAIProvider(settings),
        StateManager(store),
        SimpleKnowledgeRetriever(),
        registry,
        EventRecorder(store),
        settings=settings,
        tool_handlers=get_vedruna_tool_handlers(settings),
    )
    return orchestrator, store


def turn(
    orchestrator: ConversationOrchestrator,
    text: str,
    *,
    conversation_id: str = "v-1",
    channel: str = "whatsapp",
    confirmed: bool = False,
):
    return orchestrator.handle_turn(
        IncomingMessage(
            conversation_id=conversation_id,
            client_id="vedruna",
            channel=channel,
            text=text,
            media={"confirmation_verified": confirmed},
        )
    )
