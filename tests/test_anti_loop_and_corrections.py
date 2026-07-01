from __future__ import annotations

from core.config import Settings
from core.conversation.orchestrator import ConversationOrchestrator
from core.conversation.state_manager import StateManager
from core.knowledge.retriever import SimpleKnowledgeRetriever
from core.llm.openai_provider import OpenAIProvider
from core.llm.schemas import IncomingMessage
from core.observability.events import EventRecorder
from core.persistence.memory import MemoryStore
from core.tools.registry import ToolRegistry


def make_orchestrator() -> tuple[ConversationOrchestrator, MemoryStore]:
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
    return orchestrator, store


def test_correction_updates_info_and_does_not_repeat_previous_reply_key() -> None:
    orchestrator, store = make_orchestrator()
    first = orchestrator.handle_turn(
        IncomingMessage(
            conversation_id="corr-1",
            client_id="mudanzas_example",
            text="Necesito presupuesto de mudanza",
            channel="whatsapp",
        )
    )
    second = orchestrator.handle_turn(
        IncomingMessage(
            conversation_id="corr-1",
            client_id="mudanzas_example",
            text="me faltan 8, no una",
            channel="whatsapp",
        )
    )
    state = store.load_state("corr-1", "mudanzas_example")
    assert first.reply_key == "mudanzas_ask_origin"
    assert second.reply_key != first.reply_key
    assert state.collected_info["missing_items"] == 8


def test_information_only_and_negative_reservation_cancel_previous_flow() -> None:
    orchestrator, store = make_orchestrator()
    orchestrator.handle_turn(
        IncomingMessage(
            conversation_id="cancel-1",
            client_id="somos_perros_example",
            text="Quiero reservar para Yuyu",
            channel="whatsapp",
        )
    )
    result = orchestrator.handle_turn(
        IncomingMessage(
            conversation_id="cancel-1",
            client_id="somos_perros_example",
            text="no quiero reserva, solo informacion",
            channel="whatsapp",
        )
    )
    state = store.load_state("cancel-1", "somos_perros_example")
    assert result.action_type == "cancel_flow"
    assert result.reply_key == "information_only_ack"
    assert state.current_flow is None
    assert state.pending_action is None


def test_short_reply_uses_last_bot_question_context() -> None:
    orchestrator, _store = make_orchestrator()
    first = orchestrator.handle_turn(
        IncomingMessage(
            conversation_id="short-1",
            client_id="somos_perros_example",
            text="Quiero reservar para Yuyu",
            channel="whatsapp",
        )
    )
    second = orchestrator.handle_turn(
        IncomingMessage(
            conversation_id="short-1",
            client_id="somos_perros_example",
            text="perfecto",
            channel="whatsapp",
        )
    )
    assert first.reply_key == "perros_ask_dates"
    assert second.intent == "reservation"
    assert second.reply_key == "perros_ask_dates"
