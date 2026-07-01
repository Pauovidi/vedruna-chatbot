from __future__ import annotations

from typing import Any

from core.adapters.vedruna.domain_schema import (
    Clinic,
    appointment_duration_minutes,
    clinic_phone,
    missing_booking_fields,
    ready_for_availability,
    ready_for_create,
    requires_insurance,
    service_allowed,
    unsupported_service,
)
from core.conversation.actions import ConversationAction
from core.conversation.state_manager import ConversationState
from core.nlu.schemas import NLUResult
from core.tools.registry import ToolRegistry


def decide_vedruna_action(
    context: ConversationState,
    nlu_result: NLUResult,
    registry: ToolRegistry | None = None,
) -> ConversationAction:
    del registry
    slots = dict(context.slots)
    channel = str(context.channel_context.get("channel") or "whatsapp")
    intent = nlu_result.intent

    if intent == "greeting" and not context.active_flow:
        return _reply("vedruna_greeting", state_updates=_flow(None))

    if intent == "human_handoff":
        return _transfer_or_handoff(channel, slots.get("clinic"), "human_requested")

    if intent == "price_query":
        if channel == "voice" and slots.get("clinic"):
            return _voice_transfer(slots.get("clinic"), "price_query")
        reply_key = (
            "vedruna_price_with_clinic"
            if slots.get("clinic")
            else "vedruna_price_ask_clinic"
        )
        return _reply(reply_key, state_updates=_flow(context.active_flow))

    if intent == "urgent_request":
        if channel == "voice":
            return _voice_transfer(slots.get("clinic"), "urgent_request")
        return _reply("vedruna_urgent_whatsapp", state_updates=_flow("vedruna_appointment"))

    if intent == "unsupported_specialty" or unsupported_service(slots.get("service")):
        if channel == "voice":
            return _voice_transfer(slots.get("clinic"), "unsupported_specialty")
        return _reply("vedruna_unsupported_specialty", state_updates=_flow(None))

    if intent in {
        "faq_hours",
        "faq_location",
        "faq_services",
        "provide_insurance",
        "insurance_question",
    } and not _in_booking_flow(context):
        return _reply(_faq_reply_key(intent), state_updates=_flow(context.active_flow))

    if intent == "cancel_appointment" or context.active_flow == "vedruna_cancellation":
        return _cancellation_action(context, slots)

    if intent == "reschedule_appointment" or context.active_flow == "vedruna_reschedule":
        return _reschedule_action(context, slots)

    if intent == "recall_appointment" or context.active_flow == "vedruna_recall":
        return _recall_action(context, slots)

    if _in_booking_flow(context) or intent in _BOOKING_INTENTS:
        return _booking_action(context, slots)

    return _reply("vedruna_greeting", state_updates=_flow(None))


def _booking_action(context: ConversationState, slots: dict[str, Any]) -> ConversationAction:
    clinic = slots.get("clinic")
    service = slots.get("service")
    if not clinic:
        return _ask("vedruna_ask_clinic", "clinic")
    if not service:
        reply_key = (
            "vedruna_ask_service_madre"
            if clinic == Clinic.MADRE_VEDRUNA.value
            else "vedruna_ask_service_santa"
        )
        return _ask(reply_key, "service")
    if clinic == Clinic.SANTA_ISABEL.value and slots.get("insurance_type") == "seguro":
        return _reply(
            "vedruna_santa_isabel_particular_only",
            state_updates=_flow("vedruna_appointment"),
        )
    if not service_allowed(clinic, service):
        return _reply("vedruna_service_not_allowed", state_updates=_flow("vedruna_appointment"))
    if requires_insurance(clinic) and not slots.get("insurance_type"):
        return _ask("vedruna_ask_insurance", "insurance_type")

    missing = missing_booking_fields(slots)
    if missing:
        return _ask(_missing_reply_key(missing[0]), missing[0])

    if ready_for_create(slots):
        return ConversationAction(
            action_type="call_tool",
            reply_intent="create_appointment",
            reply_key="vedruna_creating_appointment",
            requires_tool=True,
            tool_name="rpa_create_appointment",
            tool_arguments=_create_arguments(context, slots),
            state_updates=_flow("vedruna_appointment"),
            safety_level="high",
            metadata={"vedruna_flow": "create_appointment"},
        )

    if ready_for_availability(slots):
        return ConversationAction(
            action_type="call_tool",
            reply_intent="search_availability",
            reply_key="vedruna_searching_availability",
            requires_tool=True,
            tool_name="rpa_search_availability",
            tool_arguments=_availability_arguments(context, slots),
            state_updates=_flow("vedruna_appointment"),
            safety_level="low",
            metadata={"vedruna_flow": "availability"},
        )

    return _ask("vedruna_ask_clinic", "clinic")


def _cancellation_action(
    context: ConversationState,
    slots: dict[str, Any],
) -> ConversationAction:
    if not slots.get("patient_phone"):
        return _ask(
            "vedruna_ask_phone_for_lookup",
            "patient_phone",
            flow="vedruna_cancellation",
        )
    lookup = _last_lookup(context)
    if nlu_intent(context) == "confirm_cancel_appointment" and lookup:
        return ConversationAction(
            action_type="call_tool",
            reply_intent="cancel_appointment",
            reply_key="vedruna_cancelling",
            requires_tool=True,
            tool_name="rpa_cancel_appointment",
            tool_arguments={
                "appointment_id": lookup.get("appointment_id"),
                "conversation_id": context.conversation_id,
            },
            state_updates=_flow("vedruna_cancellation"),
            safety_level="high",
            metadata={"vedruna_flow": "cancel_confirmed"},
        )
    if not lookup:
        return ConversationAction(
            action_type="call_tool",
            reply_intent="find_appointment_for_cancel",
            reply_key="vedruna_lookup_cancel",
            requires_tool=True,
            tool_name="rpa_find_appointment",
            tool_arguments=_lookup_arguments(context, slots),
            state_updates=_flow("vedruna_cancellation"),
            metadata={"vedruna_flow": "cancel_lookup"},
        )
    return _reply("vedruna_cancel_confirm_prompt", state_updates=_flow("vedruna_cancellation"))


def _reschedule_action(context: ConversationState, slots: dict[str, Any]) -> ConversationAction:
    if not slots.get("patient_phone"):
        return _ask("vedruna_ask_phone_for_lookup", "patient_phone", flow="vedruna_reschedule")
    lookup = _last_lookup(context)
    if not lookup:
        return ConversationAction(
            action_type="call_tool",
            reply_intent="find_appointment_for_reschedule",
            reply_key="vedruna_lookup_reschedule",
            requires_tool=True,
            tool_name="rpa_find_appointment",
            tool_arguments=_lookup_arguments(context, slots),
            state_updates=_flow("vedruna_reschedule"),
            metadata={"vedruna_flow": "reschedule_lookup"},
        )
    if slots.get("selected_slot_id"):
        return ConversationAction(
            action_type="call_tool",
            reply_intent="reschedule_appointment",
            reply_key="vedruna_rescheduling",
            requires_tool=True,
            tool_name="rpa_reschedule_appointment",
            tool_arguments={
                "appointment_id": lookup.get("appointment_id"),
                "new_slot_id": slots.get("selected_slot_id"),
                "conversation_id": context.conversation_id,
                "idempotency_key": (
                    f"{context.conversation_id}:reschedule:{slots.get('selected_slot_id')}"
                ),
            },
            state_updates=_flow("vedruna_reschedule"),
            safety_level="high",
            metadata={"vedruna_flow": "reschedule_confirmed"},
        )
    if slots.get("date_preference") or slots.get("time_preference"):
        return ConversationAction(
            action_type="call_tool",
            reply_intent="search_reschedule_availability",
            reply_key="vedruna_searching_availability",
            requires_tool=True,
            tool_name="rpa_search_availability",
            tool_arguments=_reschedule_availability_arguments(context, slots, lookup),
            state_updates={
                **_flow("vedruna_reschedule"),
                "tool_state": dict(context.tool_state),
            },
            metadata={"vedruna_flow": "reschedule_availability"},
        )
    return _reply("vedruna_reschedule_result", state_updates=_flow("vedruna_reschedule"))


def nlu_intent(context: ConversationState) -> str | None:
    return context.last_user_intent


def _last_lookup(context: ConversationState) -> dict[str, Any] | None:
    lookup = context.tool_state.get("last_lookup")
    return lookup if isinstance(lookup, dict) else None


def _reschedule_availability_arguments(
    context: ConversationState,
    slots: dict[str, Any],
    lookup: dict[str, Any],
) -> dict[str, Any]:
    clinic = slots.get("clinic") or lookup.get("clinic")
    service = slots.get("service") or lookup.get("service") or "podologia"
    return {
        "clinic": clinic,
        "service": service,
        "duration_minutes": appointment_duration_minutes(str(service)),
        "date_preference": slots.get("date_preference"),
        "time_preference": slots.get("time_preference"),
        "conversation_id": context.conversation_id,
    }


def _recall_action(context: ConversationState, slots: dict[str, Any]) -> ConversationAction:
    if not slots.get("patient_phone"):
        return _ask("vedruna_ask_phone_for_lookup", "patient_phone", flow="vedruna_recall")
    return ConversationAction(
        action_type="call_tool",
        reply_intent="recall_appointment",
        reply_key="vedruna_lookup_recall",
        requires_tool=True,
        tool_name="rpa_find_appointment",
        tool_arguments=_lookup_arguments(context, slots),
        state_updates=_flow("vedruna_recall"),
        metadata={"vedruna_flow": "recall_lookup"},
    )


def _transfer_or_handoff(channel: str, clinic: str | None, reason: str) -> ConversationAction:
    if channel == "voice":
        return _voice_transfer(clinic, reason)
    return ConversationAction(
        action_type="handoff_visible",
        reply_intent=reason,
        reply_key="vedruna_human_handoff",
        visible_handoff_required=True,
        requires_tool=True,
        tool_name="handoff_to_human",
        requires_human=True,
        target_role="clinical_team",
        state_updates=_flow(None),
        metadata={"vedruna_flow": "human_handoff"},
    )


def _voice_transfer(clinic: str | None, reason: str) -> ConversationAction:
    phone_number = clinic_phone(clinic)
    return ConversationAction(
        action_type="call_tool",
        reply_intent=reason,
        reply_key="vedruna_voice_transfer",
        requires_tool=True,
        tool_name="voice_transfer_call",
        tool_arguments={
            "clinic": clinic or "unknown",
            "reason": reason,
            "phone_number": phone_number,
        },
        requires_human=True,
        target_role="clinical_team",
        state_updates=_flow(None),
        metadata={"vedruna_flow": "voice_transfer"},
    )


def _reply(reply_key: str, state_updates: dict[str, Any] | None = None) -> ConversationAction:
    return ConversationAction(
        action_type="answer_information",
        reply_intent=reply_key,
        reply_key=reply_key,
        state_updates=state_updates or {},
    )


def _ask(
    reply_key: str,
    target: str,
    *,
    flow: str = "vedruna_appointment",
) -> ConversationAction:
    return ConversationAction(
        action_type="ask_missing_context",
        reply_intent=target,
        reply_key=reply_key,
        target=target,
        state_updates={**_flow(flow), "pending_fields": [target]},
    )


def _flow(name: str | None) -> dict[str, Any]:
    return {"current_flow": name, "active_flow": name, "active_topic": name}


def _in_booking_flow(context: ConversationState) -> bool:
    return (context.active_flow or context.current_flow) == "vedruna_appointment"


def _faq_reply_key(intent: str) -> str:
    return {
        "faq_hours": "vedruna_faq_hours",
        "faq_location": "vedruna_faq_location",
        "faq_services": "vedruna_faq_services",
        "provide_insurance": "vedruna_faq_insurance",
        "insurance_question": "vedruna_faq_insurance",
    }.get(intent, "vedruna_greeting")


def _missing_reply_key(field: str) -> str:
    return {
        "patient_first_name": "vedruna_ask_first_name",
        "patient_last_names": "vedruna_ask_last_names",
        "patient_phone": "vedruna_ask_phone",
        "consultation_reason": "vedruna_ask_reason",
        "date_preference": "vedruna_ask_date",
        "insurance_type": "vedruna_ask_insurance",
    }.get(field, "vedruna_ask_clinic")


def _availability_arguments(
    context: ConversationState,
    slots: dict[str, Any],
) -> dict[str, Any]:
    return {
        "clinic": slots.get("clinic"),
        "service": slots.get("service"),
        "duration_minutes": appointment_duration_minutes(slots.get("service")),
        "date_preference": slots.get("date_preference"),
        "time_preference": slots.get("time_preference"),
        "conversation_id": context.conversation_id,
    }


def _create_arguments(context: ConversationState, slots: dict[str, Any]) -> dict[str, Any]:
    return {
        "clinic": slots.get("clinic"),
        "service": slots.get("service"),
        "slot_id": slots.get("selected_slot_id"),
        "patient": {
            "first_name": slots.get("patient_first_name"),
            "last_names": slots.get("patient_last_names"),
            "phone": slots.get("patient_phone"),
        },
        "consultation_reason": slots.get("consultation_reason"),
        "insurance_type": slots.get("insurance_type"),
        "insurance_provider": slots.get("insurance_provider"),
        "duration_minutes": appointment_duration_minutes(slots.get("service")),
        "conversation_id": context.conversation_id,
        "idempotency_key": f"{context.conversation_id}:{slots.get('selected_slot_id')}",
        "agenda_title": (
            f"cita IA {slots.get('patient_first_name', '')} "
            f"{slots.get('patient_last_names', '')} {slots.get('patient_phone', '')} "
            f"{slots.get('consultation_reason', '')}"
        ).strip(),
    }


def _lookup_arguments(context: ConversationState, slots: dict[str, Any]) -> dict[str, Any]:
    return {
        "clinic": slots.get("clinic"),
        "patient_phone": slots.get("patient_phone"),
        "patient_first_name": slots.get("patient_first_name"),
        "patient_last_names": slots.get("patient_last_names"),
        "conversation_id": context.conversation_id,
    }


_BOOKING_INTENTS = {
    "book_appointment",
    "choose_clinic",
    "choose_service",
    "provide_insurance",
    "provide_patient_name",
    "provide_patient_phone",
    "provide_consultation_reason",
    "provide_date_preference",
    "provide_time_preference",
    "select_slot",
    "correction",
}
