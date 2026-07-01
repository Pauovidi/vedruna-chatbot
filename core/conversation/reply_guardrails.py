from __future__ import annotations

import re

from pydantic import BaseModel

TECHNICAL_PATTERNS = [
    re.compile(r"\btool[_ ]?[a-z0-9_]*\b", re.IGNORECASE),
    re.compile(r"\b(required_flags?|risk_level|handler|backend executor)\b", re.IGNORECASE),
    re.compile(
        r"\b(red flag|no red flag|triage|handoff|manual review|requires_manual_review)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(appointment_scope|intent|clinical priority|prioridad clinica|routing)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(confidence|fallback tecnico|dry_run|policy|state reducer|nlu)\b",
        re.IGNORECASE,
    ),
]
PRICE_PATTERN = re.compile(r"\b\d+([,.]\d+)?\s?(eur|€|euros)\b", re.IGNORECASE)


class GuardrailResult(BaseModel):
    text: str
    forbidden_claim_detected: bool = False
    reason_code: str | None = None


def validate_reply(reply: str, source_ids: list[str] | None = None) -> GuardrailResult:
    sanitized = sanitize_visible_text(reply)
    if sanitized != reply:
        return GuardrailResult(
            text=sanitized,
            forbidden_claim_detected=True,
            reason_code="technical_tool_name_leak",
        )
    if PRICE_PATTERN.search(reply) and not source_ids:
        return GuardrailResult(
            text=(
                "Para darte un precio fiable necesito revisar los datos antes. "
                "Vamos paso a paso."
            ),
            forbidden_claim_detected=True,
            reason_code="unsourced_price_claim",
        )
    return GuardrailResult(text=reply)


def sanitize_visible_text(reply: str) -> str:
    for pattern in TECHNICAL_PATTERNS:
        if pattern.search(reply):
            return "Lo revisa una persona del equipo y te responderemos de forma clara."
    return reply


def adapt_for_channel(reply: str, channel: str) -> str:
    if channel == "voice":
        return " ".join(reply.replace("\n", " ").split())[:240]
    if channel == "whatsapp":
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", reply) if part.strip()]
        return "\n".join(sentences[:3])[:360]
    return reply
