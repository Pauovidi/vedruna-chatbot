from __future__ import annotations

from dataclasses import dataclass

from core.conversation.contracts import NormalizedInbound
from core.conversation.orchestrator import ConversationOrchestrator
from core.llm.schemas import ChatTurnResult, IncomingMessage


@dataclass
class ConversationRuntimeAdapters:
    orchestrator: ConversationOrchestrator


def run_conversation_turn(
    inbound: NormalizedInbound,
    adapters: ConversationRuntimeAdapters,
) -> ChatTurnResult:
    return adapters.orchestrator.handle_turn(
        IncomingMessage(
            channel=inbound.channel,
            conversation_id=inbound.conversation_id,
            client_id=inbound.client_id,
            user_id=inbound.user_id,
            text=inbound.text,
            media=inbound.media,
            timestamp=inbound.timestamp,
        )
    )


runConversationTurn = run_conversation_turn
