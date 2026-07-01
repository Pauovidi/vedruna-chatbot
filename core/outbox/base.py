from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from core.llm.schemas import Channel


class OutboxMessage(BaseModel):
    conversation_id: str
    channel: Channel
    text: str
    reply_key: str
    action_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class OutboxResult(BaseModel):
    status: Literal["sent", "dry_run", "skipped", "failed"] = "dry_run"
    channel: Channel
    message_id: str | None = None
    safe_error_code: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Outbox(Protocol):
    def send(self, message: OutboxMessage) -> OutboxResult:
        ...


class MemoryOutbox:
    def __init__(self, *, dry_run: bool = True) -> None:
        self.dry_run = dry_run
        self.messages: list[OutboxMessage] = []

    def send(self, message: OutboxMessage) -> OutboxResult:
        self.messages.append(message.model_copy(deep=True))
        return OutboxResult(
            status="dry_run" if self.dry_run else "sent",
            channel=message.channel,
            message_id=f"outbox_{len(self.messages)}",
        )
