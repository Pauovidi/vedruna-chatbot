from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from core.conversation.state_manager import ConversationState
from core.observability.events import Event
from core.observability.redaction import redact_payload


class MemoryStore:
    store_type = "memory"
    persistence_durable = False
    ephemeral_store = True
    tables_ready = True

    def __init__(self) -> None:
        self._states: dict[str, ConversationState] = {}
        self.messages: dict[str, list[dict[str, Any]]] = {}
        self.events: list[Event] = []
        self.tool_calls: list[dict[str, Any]] = []

    def load_state(self, conversation_id: str, client_id: str) -> ConversationState:
        if conversation_id not in self._states:
            self._states[conversation_id] = ConversationState(
                conversation_id=conversation_id,
                client_id=client_id,
            )
        state = self._states[conversation_id]
        if state.client_id == "default" and client_id != "default":
            state.client_id = client_id
        return state.model_copy(deep=True)

    def save_state(self, state: ConversationState) -> None:
        self._states[state.conversation_id] = state.model_copy(deep=True)

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
        self.messages.setdefault(conversation_id, []).append(
            {
                "role": role,
                "text": text,
                "client_id": client_id,
                "channel": channel,
                "metadata": deepcopy(metadata or {}),
                "created_at": datetime.utcnow(),
            }
        )

    def list_messages(
        self,
        conversation_id: str,
        *,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        messages = deepcopy(self.messages.get(conversation_id, []))
        if limit is not None:
            return messages[-limit:]
        return messages

    def record_event(
        self,
        conversation_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        self.events.append(
            Event(
                conversation_id=conversation_id,
                type=event_type,
                payload=redact_payload(payload),
            )
        )

    def record_events(self, events: list[tuple[str, str, dict[str, Any]]]) -> None:
        for conversation_id, event_type, payload in events:
            self.record_event(conversation_id, event_type, payload)

    def list_events(self, conversation_id: str) -> list[Event]:
        return [event for event in self.events if event.conversation_id == conversation_id]

    def record_tool_call(
        self,
        conversation_id: str,
        name: str,
        status: str,
        payload: dict[str, Any],
    ) -> None:
        self.tool_calls.append(
            {
                "conversation_id": conversation_id,
                "name": name,
                "status": status,
                "payload": redact_payload(payload),
                "created_at": datetime.utcnow(),
            }
        )
