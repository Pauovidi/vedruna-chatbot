from __future__ import annotations

import json
from typing import Any

from core.conversation.contracts import NormalizedInbound


def normalize_conversationrelay_event(payload: dict[str, Any]) -> NormalizedInbound:
    event_type = str(payload.get("type") or payload.get("event") or "prompt")
    conversation_id = str(
        payload.get("callSid")
        or payload.get("CallSid")
        or payload.get("conversation_id")
        or "vedruna-voice-unknown"
    )
    text = _event_text(event_type, payload)
    media: dict[str, Any] = {"conversationrelay_event": event_type}
    if event_type == "dtmf" and payload.get("digits"):
        media["dtmf"] = str(payload["digits"])
    return NormalizedInbound(
        conversationId=conversation_id,
        clientId="vedruna",
        channel="voice",
        text=text,
        media=media,
        metadata={"source": "twilio_conversationrelay", "event_type": event_type},
    )


def conversationrelay_text_message(text: str) -> str:
    return json.dumps({"type": "text", "token": text}, ensure_ascii=False)


def _event_text(event_type: str, payload: dict[str, Any]) -> str:
    if event_type == "setup":
        return "hola"
    if event_type == "dtmf":
        return str(payload.get("digits") or "")
    return str(
        payload.get("voicePrompt")
        or payload.get("prompt")
        or payload.get("text")
        or payload.get("transcript")
        or ""
    )

