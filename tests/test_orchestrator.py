from __future__ import annotations

from core.config import Settings
from core.conversation.orchestrator import ConversationOrchestrator
from core.conversation.state_manager import StateManager
from core.knowledge.retriever import SimpleKnowledgeRetriever
from core.knowledge.schemas import KnowledgeEntry
from core.llm.openai_provider import OpenAIProvider
from core.llm.schemas import IncomingMessage
from core.observability.events import EventRecorder
from core.tools.registry import ToolRegistry


def make_orchestrator() -> ConversationOrchestrator:
    settings = Settings(OPENAI_API_KEY="", CONVERSATIONAL_REPLY_SHADOW=True)
    retriever = SimpleKnowledgeRetriever(
        [
            KnowledgeEntry(
                id="mudanzas_quote_fields",
                client_id="mudanzas_example",
                title="Datos mudanza",
                content="origen destino fecha aproximada ascensor volumen presupuesto",
                tags=["presupuesto", "mudanza"],
            ),
            KnowledgeEntry(
                id="perros_reservation_fields",
                client_id="somos_perros_example",
                title="Reserva perros",
                content="fechas entrada salida nombre perros medicacion reserva",
                tags=["reserva", "perros"],
            ),
        ]
    )
    return ConversationOrchestrator(
        OpenAIProvider(settings),
        StateManager(),
        retriever,
        ToolRegistry(),
        EventRecorder(),
    )


def test_contextual_followup_does_not_fallback() -> None:
    orchestrator = make_orchestrator()
    first = orchestrator.handle_turn(
        IncomingMessage(
            conversation_id="pain-1",
            client_id="default",
            text="tengo dolor",
            channel="webchat",
        )
    )
    second = orchestrator.handle_turn(
        IncomingMessage(
            conversation_id="pain-1",
            client_id="default",
            text="no es muy fuerte, pero molesta",
            channel="webchat",
        )
    )
    assert first.reply_text
    assert "Cuéntame un poco más" not in second.reply_text
    assert second.requires_human is False


def test_mudanzas_incomplete_quote_asks_next_field() -> None:
    result = make_orchestrator().handle_turn(
        IncomingMessage(
            conversation_id="move-1",
            client_id="mudanzas_example",
            text="Necesito presupuesto de mudanza",
            channel="whatsapp",
        )
    )
    assert "origen" in result.reply_text.lower()
    assert result.source_ids == ["mudanzas_quote_fields"]


def test_somos_perros_incomplete_dates_asks_missing_info() -> None:
    result = make_orchestrator().handle_turn(
        IncomingMessage(
            conversation_id="dog-1",
            client_id="somos_perros_example",
            text="Quiero reservar para Yuyu y Kira",
            channel="whatsapp",
        )
    )
    assert "fechas" in result.reply_text.lower()
    assert result.source_ids == ["perros_reservation_fields"]


def test_human_mode_does_not_reply() -> None:
    orchestrator = make_orchestrator()
    state = orchestrator.state_manager.load("human-1", "default")
    state.mode = "human"
    orchestrator.state_manager.save(state)
    result = orchestrator.handle_turn(
        IncomingMessage(
            conversation_id="human-1",
            client_id="default",
            text="Hola?",
            channel="webchat",
        )
    )
    assert result.reply_text == ""
    assert result.requires_human is True
    assert result.mode == "human"
