from __future__ import annotations

from core.conversation.state_manager import ConversationState


def request_handoff(state: ConversationState) -> ConversationState:
    state.mode = "human"
    return state
