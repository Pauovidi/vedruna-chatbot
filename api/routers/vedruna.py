from __future__ import annotations

import base64
import hashlib
import hmac
import json
from html import escape
from urllib.parse import parse_qsl

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
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
async def vedruna_whatsapp_webhook(request: Request) -> Response:
    settings = get_settings()
    payload = await _read_twilio_payload(request)
    if settings.twilio_validate_signature and not _valid_twilio_signature(
        url=str(request.url),
        params={key: str(value) for key, value in payload.items()},
        signature=request.headers.get("X-Twilio-Signature", ""),
        auth_token=settings.twilio_auth_token,
    ):
        raise HTTPException(status_code=403, detail="invalid_twilio_signature")
    inbound = normalize_whatsapp_payload(payload)
    result = run_conversation_turn(
        inbound,
        ConversationRuntimeAdapters(orchestrator=get_orchestrator()),
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f"<Message>{escape(result.reply_text or '')}</Message>"
        "</Response>"
    )
    return Response(content=xml, media_type="application/xml")


@router.post("/webhook/voice/conversationrelay/twiml")
def vedruna_conversationrelay_twiml() -> Response:
    settings = get_settings()
    voice_attr = (
        f' voice="{escape(settings.conversation_relay_voice)}"'
        if settings.conversation_relay_voice
        else ""
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        "<Connect>"
        f'<ConversationRelay url="{escape(settings.voice_ws_url)}" '
        f'welcomeGreeting="{escape(settings.conversation_relay_welcome_greeting)}" '
        f'language="{escape(settings.conversation_relay_language)}" '
        f'transcriptionLanguage="{escape(settings.conversation_relay_transcription_language)}" '
        f'ttsProvider="{escape(settings.conversation_relay_tts_provider)}"'
        f'{voice_attr} dtmfDetection="true" />'
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


async def _read_twilio_payload(request: Request) -> dict[str, object]:
    body = await request.body()
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            return json.loads(body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return {}
    return dict(parse_qsl(body.decode("utf-8"), keep_blank_values=True))


def _valid_twilio_signature(
    *,
    url: str,
    params: dict[str, str],
    signature: str,
    auth_token: str | None,
) -> bool:
    if not auth_token or not signature:
        return False
    signed = url + "".join(f"{key}{params[key]}" for key in sorted(params))
    digest = hmac.new(
        auth_token.encode("utf-8"),
        signed.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    expected = base64.b64encode(digest).decode("ascii")
    return hmac.compare_digest(expected, signature)
