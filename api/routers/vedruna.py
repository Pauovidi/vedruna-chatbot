from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from api.dependencies import get_orchestrator
from core.adapters.vedruna.channels.voice_conversationrelay import (
    conversationrelay_text_message,
    normalize_conversationrelay_event,
)
from core.adapters.vedruna.channels.whatsapp import normalize_whatsapp_payload
from core.config import get_settings
from core.conversation.runtime import ConversationRuntimeAdapters, run_conversation_turn

router = APIRouter()


@router.get("/__health")
def health_alias() -> dict[str, object]:
    settings = get_settings()
    return {
        "ok": True,
        "service": "vedruna-chatbot",
        "rpa_dry_run": settings.rpa_dry_run,
        "voice_ws_url_present": bool(settings.voice_ws_url),
    }


@router.post("/webhook/whatsapp/vedruna")
def vedruna_whatsapp_webhook(payload: dict[str, object]) -> dict[str, object]:
    inbound = normalize_whatsapp_payload(payload)
    result = run_conversation_turn(
        inbound,
        ConversationRuntimeAdapters(orchestrator=get_orchestrator()),
    )
    return {
        "accepted": True,
        "mode": "dry_run_outbox",
        "reply_key": result.reply_key,
        "reply_text": result.reply_text,
    }


@router.post("/webhook/voice/conversationrelay/twiml")
def vedruna_conversationrelay_twiml() -> Response:
    settings = get_settings()
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        "<Connect>"
        f'<ConversationRelay url="{settings.voice_ws_url}" language="es-ES" />'
        "</Connect>"
        "</Response>"
    )
    return Response(content=xml, media_type="application/xml")


@router.websocket("/webhook/voice/conversationrelay/ws")
async def vedruna_conversationrelay_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    orchestrator = get_orchestrator()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"type": "prompt", "text": raw}
            inbound = normalize_conversationrelay_event(payload)
            result = run_conversation_turn(
                inbound,
                ConversationRuntimeAdapters(orchestrator=orchestrator),
            )
            if result.reply_text:
                await websocket.send_text(conversationrelay_text_message(result.reply_text))
    except WebSocketDisconnect:
        return
