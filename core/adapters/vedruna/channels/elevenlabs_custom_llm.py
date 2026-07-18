from __future__ import annotations

import json
import time
from collections.abc import Iterator
from typing import Any
from uuid import uuid4

from core.adapters.vedruna.domain_schema import Clinic, clinic_phone
from core.llm.schemas import ChatTurnResult


def latest_user_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        return _message_text(message.get("content"))
    return "hola"


def completion_events(
    result: ChatTurnResult,
    *,
    model: str,
    available_tools: list[dict[str, Any]],
) -> Iterator[str]:
    completion_id = f"chatcmpl-{uuid4().hex}"
    created = int(time.time())
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
                {"role": "assistant"},
            )
        )
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
    return {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": delta,
                "finish_reason": finish_reason,
            }
        ],
    }


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
