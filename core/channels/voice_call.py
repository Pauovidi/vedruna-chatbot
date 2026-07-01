from __future__ import annotations

from core.llm.schemas import IncomingMessage


def normalize_voice(payload: dict[str, object]) -> IncomingMessage:
    return IncomingMessage(
        channel="voice",
        conversation_id=str(payload["conversation_id"]),
        client_id=str(payload.get("client_id", "default")),
        phone_redacted=str(payload.get("phone_redacted", "")),
        text=str(payload.get("text", "")),
        media=dict(payload.get("media", {})),
    )
