from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from core.observability.redaction import redact_payload
from core.persistence.base import ConversationStore


class Event(BaseModel):
    conversation_id: str
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class EventRecorder:
    def __init__(self, store: ConversationStore | None = None) -> None:
        if store is None:
            from core.persistence.memory import MemoryStore

            store = MemoryStore()
        self.store = store

    def record(self, conversation_id: str, event_type: str, payload: dict[str, Any]) -> None:
        self.store.record_event(conversation_id, event_type, redact_payload(payload))

    def record_many(self, events: list[tuple[str, str, dict[str, Any]]]) -> None:
        self.store.record_events(
            [
                (conversation_id, event_type, redact_payload(payload))
                for conversation_id, event_type, payload in events
            ]
        )

    def list_for(self, conversation_id: str) -> list[Event]:
        return self.store.list_events(conversation_id)

    def record_tool_call(
        self,
        conversation_id: str,
        name: str,
        status: str,
        payload: dict[str, Any],
    ) -> None:
        self.store.record_tool_call(
            conversation_id,
            name,
            status,
            redact_payload(payload),
        )
