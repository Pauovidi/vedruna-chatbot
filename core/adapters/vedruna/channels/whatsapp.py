from __future__ import annotations

from typing import Any

from core.conversation.contracts import NormalizedInbound


def normalize_whatsapp_payload(payload: dict[str, Any]) -> NormalizedInbound:
    conversation_id = str(
        payload.get("conversation_id")
        or payload.get("ConversationSid")
        or payload.get("From")
        or "vedruna-whatsapp-unknown"
    )
    text = str(payload.get("Body") or payload.get("text") or payload.get("message") or "")
    return NormalizedInbound(
        conversationId=conversation_id,
        clientId="vedruna",
        channel="whatsapp",
        userId=str(payload.get("From") or payload.get("user_id") or ""),
        text=text,
        metadata={"source": "whatsapp_stub", "payload_keys": sorted(payload.keys())},
    )

