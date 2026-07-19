from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Iterator
from time import perf_counter
from typing import Any
from uuid import uuid4

from core.adapters.vedruna.copy_renderer import render_vedruna_stream_buffer
from core.adapters.vedruna.domain_schema import Clinic, clinic_phone
from core.llm.schemas import ChatTurnResult

logger = logging.getLogger("uvicorn.error")


def latest_user_text(messages: list[dict[str, Any]]) -> str:
    if not messages or messages[-1].get("role") != "user":
        return ""
    return _message_text(messages[-1].get("content"))


def completion_events(
    result_factory: Callable[[], ChatTurnResult | None],
    *,
    model: str,
    available_tools: list[dict[str, Any]],
    emit_initial_buffer: bool = True,
) -> Iterator[str]:
    completion_id = f"chatcmpl-{uuid4().hex}"
    created = int(time.time())
    # Send CopyRenderer-owned buffer text before running the core. ElevenLabs
    # requires visible buffer words for slow custom LLMs, not an empty chunk.
    if emit_initial_buffer:
        yield _sse(
            _chunk(
                completion_id,
                created,
                model,
                {"role": "assistant", "content": render_vedruna_stream_buffer()},
            )
        )
    # Keep the core and its persistence lifecycle on the request thread. A
    # background worker can reuse a database session from a previous turn.
    core_started = perf_counter()
    try:
        result = result_factory()
    except Exception:
        logger.error(
            "elevenlabs_core_turn_failed elapsed_ms=%d",
            round((perf_counter() - core_started) * 1000),
        )
        raise
    if result is not None:
        trace = result.authority_trace if isinstance(result.authority_trace, dict) else {}
        timing = trace.get("timing", {})
        logger.info(
            "elevenlabs_core_turn_complete elapsed_ms=%d reply_key=%s "
            "persistence_ms=%s load_state_ms=%s tools_ms=%s",
            round((perf_counter() - core_started) * 1000),
            result.reply_key,
            timing.get("persistenceMs"),
            timing.get("loadStateMs"),
            timing.get("toolsMs"),
        )
    if result is None:
        yield _sse(
            _chunk(
                completion_id,
                created,
                model,
                {"content": ""},
            )
        )
        yield _sse(_chunk(completion_id, created, model, {}, finish_reason="stop"))
        yield "data: [DONE]\n\n"
        return
    transfer = _transfer_tool_call(result, available_tools)
    if transfer:
        yield _sse(
            _chunk(
                completion_id,
                created,
                model,
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": f"call_{uuid4().hex}",
                            "type": "function",
                            "function": {
                                "name": "transfer_to_number",
                                "arguments": json.dumps(transfer, ensure_ascii=False),
                            },
                        }
                    ],
                },
            )
        )
        yield _sse(
            _chunk(
                completion_id,
                created,
                model,
                {},
                finish_reason="tool_calls",
            )
        )
    else:
        yield _sse(
            _chunk(
                completion_id,
                created,
                model,
                {"content": result.reply_text},
            )
        )
        yield _sse(
            _chunk(completion_id, created, model, {}, finish_reason="stop")
        )
    yield "data: [DONE]\n\n"


def _transfer_tool_call(
    result: ChatTurnResult,
    available_tools: list[dict[str, Any]],
) -> dict[str, str] | None:
    if result.reply_key != "vedruna_voice_transfer":
        return None
    if not _has_transfer_tool(available_tools):
        return None
    clinic = _transfer_clinic(result)
    number = clinic_phone(clinic)
    if not number:
        return None
    return {
        "reason": result.intent or "human_handoff",
        "transfer_number": f"+34{number}",
        "client_message": "Te paso con la clinica para que puedan atenderte directamente.",
        "agent_message": "Llamada transferida desde el asistente de Vedruna.",
    }


def _transfer_clinic(result: ChatTurnResult) -> str | None:
    for tool_result in result.tool_results:
        arguments = tool_result.data.get("arguments")
        if not isinstance(arguments, dict):
            continue
        clinic = arguments.get("clinic")
        if clinic in {Clinic.MADRE_VEDRUNA.value, Clinic.SANTA_ISABEL.value}:
            return str(clinic)
    return None


def _has_transfer_tool(tools: list[dict[str, Any]]) -> bool:
    for tool in tools:
        function = tool.get("function")
        if isinstance(function, dict) and function.get("name") == "transfer_to_number":
            return True
    return False


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict) and isinstance(item.get("text"), str):
            parts.append(str(item["text"]))
    return " ".join(part.strip() for part in parts if part.strip())


def _chunk(
    completion_id: str,
    created: int,
    model: str,
    delta: dict[str, Any],
    *,
    finish_reason: str | None = None,
) -> dict[str, Any]:
    # Match the fields produced by OpenAI's ChatCompletionChunk.model_dump().
    # ElevenLabs consumes this endpoint through an OpenAI-compatible client.
    normalized_delta = {
        "content": None,
        "function_call": None,
        "refusal": None,
        "role": None,
        "tool_calls": None,
    }
    normalized_delta.update(delta)
    return {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "service_tier": None,
        "system_fingerprint": None,
        "usage": None,
        "choices": [
            {
                "index": 0,
                "delta": normalized_delta,
                "finish_reason": finish_reason,
                "logprobs": None,
            }
        ],
    }


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
