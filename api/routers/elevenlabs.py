from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from api.dependencies import get_orchestrator, get_state_manager
from core.adapters.vedruna.channels.elevenlabs_custom_llm import (
    completion_events,
    latest_user_text,
)
from core.adapters.vedruna.channels.elevenlabs_native_agent import (
    NativeAgentAuthority,
    build_native_agent_authority,
)
from core.adapters.vedruna.domain_schema import normalize_text
from core.config import get_settings
from core.llm.schemas import IncomingMessage

router = APIRouter()


class ElevenLabsChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str = "vedruna-core"
    messages: list[dict[str, Any]] = Field(default_factory=list)
    tools: list[dict[str, Any]] = Field(default_factory=list)
    user_id: str | None = None


class ElevenLabsNativeAgentTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: str = Field(min_length=1, max_length=160)
    utterance: str = Field(min_length=1, max_length=2000)
    call_sid: str | None = Field(default=None, max_length=160)


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
    user_text = latest_user_text(body.messages)
    canonical_conversation_id = f"elevenlabs:{stable_conversation_id}"
    if not user_text:
        return StreamingResponse(
            completion_events(
                lambda: None,
                model=body.model,
                available_tools=body.tools,
                emit_initial_buffer=False,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    message = IncomingMessage(
        channel="voice",
        conversation_id=canonical_conversation_id,
        client_id="vedruna",
        text=user_text,
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


@router.post("/v1/agent/turn", response_model=NativeAgentAuthority)
def elevenlabs_native_agent_turn(
    body: ElevenLabsNativeAgentTurnRequest,
    authorization: str | None = Header(default=None),
) -> NativeAgentAuthority:
    settings = get_settings()
    if not settings.elevenlabs_native_agent_enabled:
        raise HTTPException(status_code=503, detail="native_agent_not_enabled")
    _require_native_agent_auth(authorization, settings.elevenlabs_agent_api_key)
    canonical_conversation_id = f"elevenlabs-native:{body.conversation_id}"
    message = IncomingMessage(
        channel="voice",
        conversation_id=canonical_conversation_id,
        client_id="vedruna",
        text=body.utterance,
        media={
            "source": "elevenlabs_native_agent",
            "suppress_visible_copy": True,
            "confirmation_verified": _is_explicit_confirmation(body.utterance),
            "call_sid": body.call_sid,
        },
    )
    result = get_orchestrator().handle_turn(message)
    state = get_state_manager().load(canonical_conversation_id, "vedruna")
    return build_native_agent_authority(result, state, settings)


def _require_auth(authorization: str | None, expected_key: str | None) -> None:
    if not expected_key:
        raise HTTPException(status_code=503, detail="custom_llm_not_configured")
    prefix = "Bearer "
    if not authorization or not authorization.startswith(prefix):
        raise HTTPException(status_code=401, detail="invalid_custom_llm_auth")
    supplied = authorization[len(prefix) :]
    if not hmac.compare_digest(supplied, expected_key):
        raise HTTPException(status_code=401, detail="invalid_custom_llm_auth")


def _require_native_agent_auth(
    authorization: str | None,
    expected_key: str | None,
) -> None:
    """Accept ElevenLabs server-tool secrets without weakening Custom LLM auth."""
    if not expected_key:
        raise HTTPException(status_code=503, detail="native_agent_not_configured")
    if not authorization:
        raise HTTPException(status_code=401, detail="invalid_native_agent_auth")
    supplied = authorization.removeprefix("Bearer ")
    if not hmac.compare_digest(supplied, expected_key):
        raise HTTPException(status_code=401, detail="invalid_native_agent_auth")


def _is_explicit_confirmation(utterance: str) -> bool:
    normalized = normalize_text(utterance)
    return normalized in {
        "si",
        "si confirmo",
        "confirmo",
        "confirmalo",
        "confirmar",
        "de acuerdo confirmo",
        "adelante confirmo",
    }
