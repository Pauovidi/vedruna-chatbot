from __future__ import annotations

from core.llm.schemas import IncomingMessage


def normalize_whatsapp(payload: dict[str, object]) -> IncomingMessage:
    return IncomingMessage(
        channel="whatsapp",
        conversation_id=str(payload["conversation_id"]),
        client_id=str(payload.get("client_id", "default")),
        phone_redacted=str(payload.get("phone_redacted", "")),
        text=str(payload.get("text", "")),
        media=dict(payload.get("media", {})),
    )
