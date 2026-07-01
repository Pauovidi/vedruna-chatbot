from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from core.conversation.state_manager import ConversationState
    from core.observability.events import Event


class ConversationStore(Protocol):
    store_type: str
    persistence_durable: bool
    ephemeral_store: bool
    tables_ready: bool

    def load_state(self, conversation_id: str, client_id: str) -> ConversationState:
        ...

    def save_state(self, state: ConversationState) -> None:
        ...

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
        ...

    def list_messages(
        self,
        conversation_id: str,
        *,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        ...

    def record_event(
        self,
        conversation_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        ...

    def list_events(self, conversation_id: str) -> list[Event]:
        ...

    def record_tool_call(
        self,
        conversation_id: str,
        name: str,
        status: str,
        payload: dict[str, Any],
    ) -> None:
        ...
