from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from core.conversation.state_manager import ConversationState
from core.observability.events import Event
from core.observability.redaction import redact_payload
from core.persistence.models import (
    Base,
    ConversationRecord,
    EventRecord,
    MessageRecord,
    ToolCallRecord,
)


class SQLAlchemyConversationStore:
    persistence_durable: bool
    ephemeral_store = False

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.store_type = "postgres" if database_url.startswith("postgres") else "sqlite"
        self.persistence_durable = self.store_type == "postgres"
        connect_args = {"check_same_thread": False} if self.store_type == "sqlite" else {}
        self.engine: Engine = create_engine(database_url, connect_args=connect_args)
        Base.metadata.create_all(self.engine)
        self._session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.tables_ready = True

    def load_state(self, conversation_id: str, client_id: str) -> ConversationState:
        with self._session_factory() as session:
            record = session.get(ConversationRecord, conversation_id)
            if record is None:
                state = ConversationState(conversation_id=conversation_id, client_id=client_id)
                self._upsert_state(session, state)
                session.commit()
                return state
            payload = dict(record.state or {})
            payload.update(
                {
                    "conversation_id": record.id,
                    "client_id": record.client_id,
                    "mode": record.mode,
                    "active_topic": record.active_topic,
                }
            )
            return ConversationState.model_validate(payload)

    def save_state(self, state: ConversationState) -> None:
        with self._session_factory() as session:
            self._upsert_state(session, state)
            session.commit()

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
        with self._session_factory() as session:
            session.add(
                MessageRecord(
                    conversation_id=conversation_id,
                    client_id=client_id,
                    role=role,
                    channel=channel,
                    text=text,
                    message_metadata=metadata or {},
                )
            )
            session.commit()

    def list_messages(
        self,
        conversation_id: str,
        *,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            stmt = (
                select(MessageRecord)
                .where(MessageRecord.conversation_id == conversation_id)
                .order_by(MessageRecord.id.asc())
            )
            records = list(session.scalars(stmt))
            if limit is not None:
                records = records[-limit:]
            return [
                {
                    "role": record.role,
                    "text": record.text,
                    "client_id": record.client_id,
                    "channel": record.channel,
                    "metadata": dict(record.message_metadata or {}),
                    "created_at": record.created_at,
                }
                for record in records
            ]

    def record_event(
        self,
        conversation_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        with self._session_factory() as session:
            session.add(
                EventRecord(
                    conversation_id=conversation_id,
                    type=event_type,
                    payload=redact_payload(payload),
                )
            )
            session.commit()

    def record_events(self, events: list[tuple[str, str, dict[str, Any]]]) -> None:
        if not events:
            return
        with self._session_factory() as session:
            session.add_all(
                [
                    EventRecord(
                        conversation_id=conversation_id,
                        type=event_type,
                        payload=redact_payload(payload),
                    )
                    for conversation_id, event_type, payload in events
                ]
            )
            session.commit()

    def list_events(self, conversation_id: str) -> list[Event]:
        with self._session_factory() as session:
            stmt = (
                select(EventRecord)
                .where(EventRecord.conversation_id == conversation_id)
                .order_by(EventRecord.id.asc())
            )
            return [
                Event(
                    conversation_id=record.conversation_id,
                    type=record.type,
                    payload=dict(record.payload or {}),
                    created_at=record.created_at,
                )
                for record in session.scalars(stmt)
            ]

    def record_tool_call(
        self,
        conversation_id: str,
        name: str,
        status: str,
        payload: dict[str, Any],
    ) -> None:
        with self._session_factory() as session:
            session.add(
                ToolCallRecord(
                    conversation_id=conversation_id,
                    name=name,
                    status=status,
                    payload=redact_payload(payload),
                )
            )
            session.commit()

    def _upsert_state(self, session: Session, state: ConversationState) -> None:
        record = session.get(ConversationRecord, state.conversation_id)
        payload = state.model_dump(mode="json")
        if record is None:
            session.add(
                ConversationRecord(
                    id=state.conversation_id,
                    client_id=state.client_id,
                    mode=state.mode,
                    active_topic=state.active_topic,
                    state=payload,
                )
            )
            return
        record.client_id = state.client_id
        record.mode = state.mode
        record.active_topic = state.active_topic
        record.state = payload
