from __future__ import annotations

from core.llm.schemas import IncomingMessage


def normalize_webchat(payload: dict[str, object]) -> IncomingMessage:
    return IncomingMessage(
        channel="webchat",
        conversation_id=str(payload["conversation_id"]),
        client_id=str(payload.get("client_id", "default")),
        user_id=str(payload.get("user_id", "")),
        text=str(payload.get("text", "")),
    )
