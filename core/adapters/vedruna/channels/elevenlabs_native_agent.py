from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from core.config import Settings
from core.conversation.state_manager import ConversationState
from core.llm.schemas import ChatTurnResult


class NativeAgentToolResult(BaseModel):
    name: str
    status: Literal["success", "blocked", "failed", "dry_run"]
    dry_run: bool = False
    confirmation_required: bool = False


class NativeAgentAuthority(BaseModel):
    """Machine-readable constraints for an ElevenLabs native agent.

    This is deliberately not patient-facing copy. The native agent owns phrasing;
    the core owns the fields, state transitions, tool permissions, and outcomes.
    """

    conversation_id: str
    reply_key: str | None = None
    next_step: str
    pending_fields: list[str] = Field(default_factory=list)
    collected_fields: list[str] = Field(default_factory=list)
    clinic: str | None = None
    service: str | None = None
    insurance_type: str | None = None
    offered_slots: list[dict[str, str]] = Field(default_factory=list)
    requires_explicit_confirmation: bool = False
    handoff_required: bool = False
    rpa_mode: Literal["dry_run", "live"]
    tool_results: list[NativeAgentToolResult] = Field(default_factory=list)
    constraints: list[str] = Field(
        default_factory=lambda: [
            "Never quote prices.",
            (
                "Never claim an appointment exists or is confirmed without a "
                "successful core tool result."
            ),
            "Never diagnose or triage clinically.",
            "Santa Isabel is particular-only.",
        ]
    )


def build_native_agent_authority(
    result: ChatTurnResult,
    state: ConversationState,
    settings: Settings,
) -> NativeAgentAuthority:
    tool_results = [
        NativeAgentToolResult(
            name=tool_result.name,
            status=tool_result.status,
            dry_run=bool(tool_result.data.get("dry_run")),
            confirmation_required=(
                tool_result.status == "blocked"
                and tool_result.internal_code == "confirmation_required"
            ),
        )
        for tool_result in result.tool_results
    ]
    confirmation_required = any(
        tool_result.confirmation_required for tool_result in tool_results
    )
    return NativeAgentAuthority(
        conversation_id=result.conversation_id,
        reply_key=result.reply_key,
        next_step=_next_step(result, state, confirmation_required),
        pending_fields=list(state.pending_fields),
        collected_fields=sorted(
            field
            for field, value in state.slots.items()
            if value and field in _BOOKING_FIELDS
        ),
        clinic=_string_slot(state, "clinic"),
        service=_string_slot(state, "service"),
        insurance_type=_string_slot(state, "insurance_type"),
        offered_slots=_offered_slots(state),
        requires_explicit_confirmation=confirmation_required,
        handoff_required=result.requires_human,
        rpa_mode="dry_run" if settings.rpa_dry_run else "live",
        tool_results=tool_results,
    )


_BOOKING_FIELDS = {
    "clinic",
    "service",
    "insurance_type",
    "patient_first_name",
    "patient_last_names",
    "patient_phone",
    "consultation_reason",
    "date_preference",
    "time_preference",
    "selected_slot_id",
}


def _next_step(
    result: ChatTurnResult,
    state: ConversationState,
    confirmation_required: bool,
) -> str:
    if confirmation_required:
        return "request_explicit_confirmation"
    if result.requires_human:
        return "handoff_or_provide_clinic_contact"
    if result.reply_key == "vedruna_offer_slots":
        return "present_offered_slots"
    if state.pending_fields:
        return "collect_missing_booking_field"
    if result.reply_key == "vedruna_confirm_appointment":
        return "report_confirmed_appointment"
    if result.reply_key == "vedruna_create_dry_run_notice":
        return "report_dry_run_suppressed"
    return "continue_conversation"


def _string_slot(state: ConversationState, name: str) -> str | None:
    value = state.slots.get(name)
    return str(value) if value else None


def _offered_slots(state: ConversationState) -> list[dict[str, str]]:
    raw_slots = state.tool_state.get("last_offered_slots")
    if not isinstance(raw_slots, list):
        return []
    safe_slots: list[dict[str, str]] = []
    for raw_slot in raw_slots[:3]:
        if not isinstance(raw_slot, dict):
            continue
        safe_slot = {
            key: str(raw_slot[key])
            for key in ("slot_id", "date", "time", "start")
            if raw_slot.get(key)
        }
        if safe_slot:
            safe_slots.append(safe_slot)
    return safe_slots
