from __future__ import annotations

import re
from typing import Any

from core.adapters.vedruna.domain_schema import (
    normalize_clinic,
    normalize_date_preference,
    normalize_insurance,
    normalize_service,
    normalize_text,
    normalize_time_preference,
)
from core.knowledge.schemas import KnowledgeSnippet
from core.llm.schemas import IncomingMessage
from core.nlu.schemas import NLUResult
from core.tools.schemas import ToolDefinition

PHONE_RE = re.compile(r"(?<!\d)(?:\+?34\s*)?(\d[\d\s().-]{7,}\d)(?!\d)")
NAME_RE = re.compile(
    r"\b(?:me llamo|soy)\s+([^\d\W_]+(?:\s+[^\d\W_]+){0,3})",
    re.IGNORECASE,
)
FAQ_INTENTS = {
    "price_query",
    "insurance_question",
    "faq_hours",
    "faq_location",
    "faq_services",
}


def interpret_vedruna_message(
    message: IncomingMessage,
    context: dict[str, object],
    snippets: list[KnowledgeSnippet],
    tools: list[ToolDefinition],
) -> NLUResult:
    del snippets, tools
    normalized = normalize_text(message.text)
    slots: dict[str, Any] = {}
    target_slots: dict[str, Any] = {}
    entities: dict[str, Any] = {}
    signals: list[str] = []
    tone_hints: list[str] = []

    previous_slots = context.get("slots")
    if not isinstance(previous_slots, dict):
        previous_slots = {}

    clinic = normalize_clinic(message.text)
    if clinic:
        slots["clinic"] = clinic
        target_slots["clinic"] = {"slot": "clinic"}

    service = normalize_service(message.text, clinic or previous_slots.get("clinic"))
    if service == "otro_problema" and previous_slots.get("service"):
        service = None
    if service:
        slots["service"] = service
        slots["appointment_duration_minutes"] = (
            30 if service == "estudio_biomecanico" else 20
        )
        target_slots["service"] = {"slot": "service"}
        target_slots["appointment_duration_minutes"] = {"slot": "appointment_duration_minutes"}

    insurance = normalize_insurance(message.text)
    if insurance:
        slots.update(insurance)
        target_slots["insurance_type"] = {"slot": "insurance_type"}
        target_slots["insurance_provider"] = {"slot": "insurance_provider"}

    date_preference = normalize_date_preference(message.text)
    if date_preference:
        slots["date_preference"] = date_preference
        target_slots["date_preference"] = {"slot": "date_preference"}

    time_preference = normalize_time_preference(message.text)
    if time_preference:
        slots["time_preference"] = time_preference
        target_slots["time_preference"] = {"slot": "time_preference"}

    phone = _extract_phone(message.text)
    if phone:
        slots["patient_phone"] = phone
        target_slots["patient_phone"] = {"slot": "patient_phone"}

    name = _extract_name(message.text)
    if name:
        first_name, last_names = name
        slots["patient_first_name"] = first_name
        if last_names:
            slots["patient_last_names"] = last_names
        target_slots["patient_first_name"] = {"slot": "patient_first_name"}
        target_slots["patient_last_names"] = {"slot": "patient_last_names"}

    selected_slot_id = _selected_slot_from_message(message, context)
    if selected_slot_id:
        slots["selected_slot_id"] = selected_slot_id
        target_slots["selected_slot_id"] = {"slot": "selected_slot_id"}

    if _looks_like_consultation_reason(normalized, service):
        slots.setdefault("consultation_reason", message.text.strip())
        target_slots["consultation_reason"] = {"slot": "consultation_reason"}

    intent = _intent(normalized, slots, context)
    if intent in FAQ_INTENTS:
        signals.append("faq")
    if intent == "human_handoff":
        signals.append("human_requested")
    if intent == "urgent_request":
        signals.append("urgent_request")
        tone_hints.append("urgent")
    if intent == "correction":
        signals.append("correction")
        entities["correction_slot_names"] = list(slots)

    active_topic_hint = _active_topic(intent, context)

    return NLUResult(
        intent=intent,
        global_intent=_global_intent(intent, signals),
        domain_intent=intent,
        confidence=_confidence(intent, slots),
        entities=entities,
        slots=slots,
        target_slots=target_slots,
        signals=signals,
        raw_user_reply_type="short_reply" if _short_reply(normalized) else "free_text",
        contextual_reply_to_last_question=bool(
            context.get("last_bot_question")
        )
        and _short_reply(normalized),
        active_topic_hint=active_topic_hint,
        is_information_only=False,
        is_negative_appointment=intent == "stop",
        is_price_question=intent == "price_query",
        safety_signals=[],
        safety={
            "can_write_state": False,
            "can_render_user_text": False,
            "can_call_tools": False,
        },
        ambiguity={"level": "low" if intent != "unknown" else "medium"},
        language="es",
        tone_hints=tone_hints,
    )


def _intent(normalized: str, slots: dict[str, Any], context: dict[str, object]) -> str:
    if any(term in normalized for term in ["precio", "cuanto cuesta", "coste", "tarifa"]):
        return "price_query"
    if any(term in normalized for term in ["persona", "humano", "operador"]):
        return "human_handoff"
    if any(term in normalized for term in ["urgente", "urgencia", "emergencia"]):
        return "urgent_request"
    if "traumatolog" in normalized or "psicolog" in normalized:
        return "unsupported_specialty"
    if any(term in normalized for term in ["cancelar", "anular"]):
        return "cancel_appointment"
    if any(
        term in normalized
        for term in ["modificar", "cambiar cita", "mover cita", "reagendar"]
    ):
        return "reschedule_appointment"
    if any(
        term in normalized
        for term in ["cuando tenia", "recordar cita", "mi cita", "que cita tengo"]
    ):
        return "recall_appointment"
    if any(term in normalized for term in ["horario", "abren", "abre"]):
        return "faq_hours"
    if any(term in normalized for term in ["direccion", "donde", "ubicacion"]):
        return "faq_location"
    if any(term in normalized for term in ["servicio", "que haceis", "que hacéis"]):
        return "faq_services"
    if any(term in normalized for term in ["seguro", "sanitas", "generali", "particular"]):
        current_flow = context.get("active_flow") or context.get("current_flow")
        if current_flow == "vedruna_appointment" or any(
            term in normalized for term in ["cita", "reservar", "quiero ir", "consulta"]
        ):
            return "provide_insurance"
        return "insurance_question"
    if normalized.startswith(("no ", "no,")):
        return "correction"
    if slots.get("selected_slot_id"):
        return "select_slot"
    if slots.get("clinic") and len(slots) == 1:
        return "choose_clinic"
    if slots.get("service") and len(slots) == 1:
        return "choose_service"
    if slots.get("patient_phone"):
        return "provide_patient_phone"
    if slots.get("patient_first_name"):
        return "provide_patient_name"
    if slots.get("date_preference") or slots.get("time_preference"):
        return "provide_date_preference"
    if any(term in normalized for term in ["hola", "buenos dias", "buenas"]):
        return "greeting"
    if any(term in normalized for term in ["cita", "reservar", "quiero ir", "consulta"]):
        return "book_appointment"
    current_flow = context.get("active_flow") or context.get("current_flow")
    if current_flow == "vedruna_appointment":
        return "book_appointment"
    return "unknown"


def _active_topic(intent: str, context: dict[str, object]) -> str | None:
    if intent in {
        "book_appointment",
        "choose_clinic",
        "choose_service",
        "provide_insurance",
        "provide_patient_name",
        "provide_patient_phone",
        "provide_date_preference",
        "select_slot",
        "correction",
    }:
        return "vedruna_appointment"
    if intent == "cancel_appointment":
        return "vedruna_cancellation"
    if intent == "reschedule_appointment":
        return "vedruna_reschedule"
    if intent == "recall_appointment":
        return "vedruna_recall"
    current = context.get("active_flow") or context.get("current_flow")
    if isinstance(current, str) and current.startswith("vedruna_"):
        return current
    return None


def _global_intent(intent: str, signals: list[str]) -> str | None:
    if intent in FAQ_INTENTS:
        return "faq"
    if "human_requested" in signals:
        return "handoff"
    if intent == "correction":
        return "correction"
    return None


def _confidence(intent: str, slots: dict[str, Any]) -> float:
    if intent in {"unknown", "greeting"} and not slots:
        return 0.62
    if slots:
        return 0.86
    return 0.78


def _extract_phone(text: str) -> str | None:
    match = PHONE_RE.search(text)
    if not match:
        return None
    return re.sub(r"\D", "", match.group(1))[-9:]


def _extract_name(text: str) -> tuple[str, str | None] | None:
    match = NAME_RE.search(text)
    if not match:
        return None
    parts = match.group(1).strip().split()
    if not parts:
        return None
    return parts[0].title(), " ".join(part.title() for part in parts[1:]) or None


def _selected_slot_from_message(
    message: IncomingMessage,
    context: dict[str, object],
) -> str | None:
    dtmf = message.media.get("dtmf") if isinstance(message.media, dict) else None
    normalized = normalize_text(message.text)
    index: int | None = None
    if dtmf in {"1", "2"}:
        index = int(dtmf)
    elif normalized in {"1", "primera", "la primera", "opcion 1", "opcion uno"}:
        index = 1
    elif normalized in {"2", "segunda", "la segunda", "opcion 2", "opcion dos"}:
        index = 2
    if index is None:
        return None
    tool_state = context.get("tool_state")
    if isinstance(tool_state, dict):
        offered = tool_state.get("last_offered_slots")
        if isinstance(offered, list) and 0 < index <= len(offered):
            candidate = offered[index - 1]
            if isinstance(candidate, dict) and candidate.get("slot_id"):
                return str(candidate["slot_id"])
    return f"selected_option_{index}"


def _looks_like_consultation_reason(normalized: str, service: str | None) -> bool:
    del service
    return any(term in normalized for term in ["dolor", "molestia", "callo", "dureza"])


def _short_reply(normalized: str) -> bool:
    return normalized in {"si", "no", "ok", "vale", "primera", "segunda", "1", "2"}
