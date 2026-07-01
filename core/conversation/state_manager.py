from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from core.persistence.base import ConversationStore


class ConversationState(BaseModel):
    conversation_id: str
    mode: Literal["bot", "human"] = "bot"
    active_topic: str | None = None
    active_flow: str | None = None
    current_flow: str | None = None
    last_user_intent: str | None = None
    last_bot_action: str | None = None
    last_bot_question: str | None = None
    last_question_kind: str | None = None
    pending_action: dict[str, Any] | None = None
    pending_fields: list[str] = Field(default_factory=list)
    handoff_pending: bool = False
    handoff_visible_sent: bool = False
    information_only: bool = False
    price_question_pending: bool = False
    last_reply_key: str | None = None
    recent_reply_keys: list[str] = Field(default_factory=list)
    collected_info: dict[str, Any] = Field(default_factory=dict)
    slots: dict[str, Any] = Field(default_factory=dict)
    client_status: Literal["unknown", "known", "ambiguous", "blocked"] = "unknown"
    tool_state: dict[str, Any] = Field(default_factory=dict)
    audit: dict[str, Any] = Field(default_factory=dict)
    channel_context: dict[str, Any] = Field(default_factory=dict)
    recent_context_summary: str = ""
    last_assistant_question: str | None = None
    client_id: str = "default"
    flags: dict[str, bool] = Field(default_factory=dict)


class StateManager:
    def __init__(self, store: ConversationStore | None = None) -> None:
        if store is None:
            from core.persistence.memory import MemoryStore

            store = MemoryStore()
        self.store = store

    def load(self, conversation_id: str, client_id: str) -> ConversationState:
        return self.store.load_state(conversation_id, client_id)

    def save(self, state: ConversationState) -> None:
        self.store.save_state(state)

    def append_message(
        self,
        conversation_id: str,
        role: str,
        text: str,
        *,
        client_id: str | None = None,
        channel: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.store.append_message(
            conversation_id,
            role,
            text,
            client_id=client_id,
            channel=channel,
            metadata=metadata,
        )

    def list_messages(
        self,
        conversation_id: str,
        *,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        return self.store.list_messages(conversation_id, limit=limit)

    @property
    def messages(self) -> dict[str, list[dict[str, Any]]]:
        return getattr(self.store, "messages", {})
