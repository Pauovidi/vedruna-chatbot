from __future__ import annotations

import re
import unicodedata
from typing import Any

from core.adapters.vedruna import VEDRUNA_CLIENT_ID
from core.adapters.vedruna.nlu import interpret_vedruna_message
from core.knowledge.schemas import KnowledgeSnippet
from core.llm.schemas import IncomingMessage
from core.nlu.schemas import NLUResult
from core.tools.schemas import ToolDefinition

SHORT_REPLY_RE = re.compile(r"^(si|sí|ok|vale|perfecto|no|depende|me da igual|claro)[.! ]*$")
NUMBER_RE = re.compile(r"\b(\d{1,3})\b")
TIME_RE = re.compile(r"\b(?:a las|sobre las|at)?\s*(\d{1,2})(?::(\d{2}))?\b")


class DeterministicNLUInterpreter:
    def interpret(
        self,
        message: IncomingMessage,
        context: dict[str, object],
        snippets: list[KnowledgeSnippet],
        tools: list[ToolDefinition],
    ) -> NLUResult:
        if message.client_id == VEDRUNA_CLIENT_ID:
            return interpret_vedruna_message(message, context, snippets, tools)
        del snippets, tools
        normalized = _normalize(message.text)
        entities: dict[str, Any] = {}
        signals: list[str] = []
        safety_signals: list[str] = []
        tone_hints: list[str] = []

        if "solo informacion" in normalized or "solo info" in normalized:
            signals.append("information_only")
        negative_flow_terms = [
            "no quiero cita",
            "no quiero reserva",
            "no quiero seguir",
            "no seguir",
            "no era eso",
        ]
        if any(text in normalized for text in negative_flow_terms):
            signals.append("negative_flow")
        price_terms = ["cuanto cuesta", "precio", "coste", "tarifa", "pago"]
        if any(text in normalized for text in price_terms):
            signals.append("price_question")
        if any(text in normalized for text in ["enfadado", "nadie me contesta", "queja"]):
            safety_signals.append("complaint")
            tone_hints.append("calm")
        if any(text in normalized for text in ["borra mis datos", "privacidad", "gdpr"]):
            safety_signals.append("privacy_review")
        if any(text in normalized for text in ["urgente", "emergencia", "riesgo"]):
            safety_signals.append("red_flag")
            tone_hints.append("urgent")
        if any(text in normalized for text in ["persona", "humano", "equipo"]):
            signals.append("human_requested")

        numbers = [int(match.group(1)) for match in NUMBER_RE.finditer(normalized)]
        if numbers:
            entities["numbers"] = numbers
        slots: dict[str, Any] = {}
        target_slots: dict[str, Any] = {}
        if "pasado manana" in normalized:
            slots["date"] = "relative_day_after_tomorrow"
            target_slots["date"] = "currentPending"
        elif "manana" in normalized:
            slots["date"] = "relative_tomorrow"
            target_slots["date"] = "currentPending"
        if "misma hora" in normalized or "same time" in normalized:
            slots["time"] = "same_time"
            target_slots["time"] = "currentPending"
        else:
            time_value = _extract_time(normalized)
            if time_value:
                slots["time"] = time_value
                target_slots["time"] = "currentPending"
        if "faltan" in normalized or "pieza" in normalized or "piezas" in normalized:
            signals.append("correction")
            if numbers:
                entities["missing_items"] = numbers[-1]
        if normalized.startswith(("no, ", "no ")) or "no una" in normalized:
            signals.append("correction")

        raw_reply_type = "short_reply" if SHORT_REPLY_RE.match(normalized) else "free_text"
        contextual = bool(
            context.get("last_bot_question") or context.get("last_assistant_question")
        )
        active_topic_hint = _active_topic_hint(normalized, message.client_id, context)
        intent = _intent(normalized, active_topic_hint, signals, safety_signals)

        return NLUResult(
            intent=intent,
            global_intent=_global_intent(intent, signals, safety_signals),
            domain_intent=active_topic_hint,
            confidence=_confidence(intent, raw_reply_type),
            entities=entities,
            slots={**entities, **slots},
            target_slots=target_slots,
            signals=signals,
            raw_user_reply_type=raw_reply_type,
            contextual_reply_to_last_question=contextual and raw_reply_type == "short_reply",
            active_topic_hint=active_topic_hint,
            is_information_only="information_only" in signals,
            is_negative_appointment="negative_flow" in signals,
            is_price_question="price_question" in signals,
            safety_signals=safety_signals,
            safety={
                "can_write_state": False,
                "can_render_user_text": False,
                "can_call_tools": False,
            },
            ambiguity={"level": "low" if intent != "unknown" else "medium"},
            language="es",
            tone_hints=tone_hints,
        )


def _intent(
    normalized: str,
    active_topic_hint: str | None,
    signals: list[str],
    safety_signals: list[str],
) -> str:
    if "privacy_review" in safety_signals:
        return "privacy_request"
    if "complaint" in safety_signals:
        return "complaint"
    if "red_flag" in safety_signals:
        return "needs_attention"
    if "information_only" in signals:
        return "information_only"
    if "negative_flow" in signals:
        return "cancel_or_stop_flow"
    if "price_question" in signals:
        return "price_question"
    if "correction" in signals:
        return "correction"
    if any(text in normalized for text in ["cancelar", "anular"]):
        return "critical_change_request"
    if active_topic_hint:
        return active_topic_hint
    return "general"


def _active_topic_hint(
    normalized: str,
    client_id: str,
    context: dict[str, object],
) -> str | None:
    if client_id == "mudanzas_example" or any(
        word in normalized for word in ["mudanza", "presupuesto", "cajas", "origen", "destino"]
    ):
        return "quote_lead"
    if client_id == "somos_perros_example" or any(
        word in normalized
        for word in ["reservar", "reserva", "perro", "entrada", "salida", "fechas"]
    ):
        return "reservation"
    current_flow = context.get("current_flow") or context.get("active_topic")
    return str(current_flow) if current_flow else None


def _confidence(intent: str, raw_reply_type: str) -> float:
    if intent in {"privacy_request", "complaint", "needs_attention"}:
        return 0.86
    if intent in {"quote_lead", "reservation", "price_question"}:
        return 0.78
    if raw_reply_type == "short_reply":
        return 0.58
    return 0.62


def _global_intent(
    intent: str,
    signals: list[str],
    safety_signals: list[str],
) -> str | None:
    if intent in {"information_only", "cancel_or_stop_flow"}:
        return "cancel_flow"
    if intent in {"privacy_request", "complaint"} or "human_requested" in signals:
        return "handoff"
    if "red_flag" in safety_signals:
        return "red_flag"
    if intent == "correction":
        return "correction"
    if intent == "price_question":
        return "faq"
    return None


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", value.lower())
    return "".join(char for char in text if not unicodedata.combining(char)).strip()


def _extract_time(normalized: str) -> str | None:
    if "a las" not in normalized and "sobre las" not in normalized and " at " not in normalized:
        return None
    match = TIME_RE.search(normalized)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"
