from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from api.dependencies import get_orchestrator
from core.adapters.vedruna.channels.elevenlabs_custom_llm import (
    completion_events,
    latest_user_text,
)
from core.config import get_settings
from core.llm.schemas import IncomingMessage

router = APIRouter()


class ElevenLabsChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str = "vedruna-core"
    messages: list[dict[str, Any]] = Field(default_factory=list)
    tools: list[dict[str, Any]] = Field(default_factory=list)
    user_id: str | None = None


@router.post("/v1/chat/completions")
def elevenlabs_chat_completions(
    body: ElevenLabsChatCompletionRequest,
    authorization: str | None = Header(default=None),
    conversation_id: str | None = Header(
        default=None,
        alias="X-ElevenLabs-Conversation-ID",
    ),
) -> StreamingResponse:
    settings = get_settings()
    _require_auth(authorization, settings.elevenlabs_custom_llm_api_key)
    stable_conversation_id = conversation_id or body.user_id
    if not stable_conversation_id:
        raise HTTPException(status_code=400, detail="missing_conversation_id")
    message = IncomingMessage(
        channel="voice",
        conversation_id=f"elevenlabs:{stable_conversation_id}",
        client_id="vedruna",
        text=latest_user_text(body.messages),
        media={"source": "elevenlabs_custom_llm"},
    )
    return StreamingResponse(
        completion_events(
            lambda: get_orchestrator().handle_turn(message),
            model=body.model,
            available_tools=body.tools,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _require_auth(authorization: str | None, expected_key: str | None) -> None:
    if not expected_key:
        raise HTTPException(status_code=503, detail="custom_llm_not_configured")
    prefix = "Bearer "
    if not authorization or not authorization.startswith(prefix):
        raise HTTPException(status_code=401, detail="invalid_custom_llm_auth")
    supplied = authorization[len(prefix) :]
    if not hmac.compare_digest(supplied, expected_key):
        raise HTTPException(status_code=401, detail="invalid_custom_llm_auth")
