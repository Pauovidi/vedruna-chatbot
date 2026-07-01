from __future__ import annotations

from pydantic import BaseModel, Field

from core.conversation.actions import ConversationAction
from core.conversation.state_manager import ConversationState
from core.llm.schemas import ToolResult
from core.nlu.schemas import NLUResult


class AuthorityInvariantReport(BaseModel):
    renderer_uses_state_after: bool = True
    pending_fields_from_state_after: list[str] = Field(default_factory=list)
    useful_slots_accounted: bool = True
    critical_tool_success_required: bool = True
    active_flow_preserved_for_global_faq: bool = True
    violations: list[str] = Field(default_factory=list)


def enforce_authority_invariants(
    *,
    state_before: ConversationState,
    state_after: ConversationState,
    nlu_result: NLUResult,
    action: ConversationAction,
    applied_slots: list[str],
    ignored_slot_reasons: dict[str, str],
    tool_results: list[ToolResult],
) -> AuthorityInvariantReport:
    violations: list[str] = []
    useful_slots = {
        name
        for name, value in nlu_result.slots.items()
        if value not in (None, "")
    }
    accounted = set(applied_slots) | set(ignored_slot_reasons)
    missing_accounting = sorted(useful_slots - accounted - set(state_after.slots))
    if missing_accounting:
        violations.append(f"useful_slots_unaccounted:{','.join(missing_accounting)}")

    if (
        nlu_result.global_intent == "faq"
        and state_before.active_flow
        and state_after.active_flow != state_before.active_flow
    ):
        violations.append("global_faq_dropped_active_flow")

    critical_action = action.safety_level == "critical" or bool(
        action.metadata.get("critical_action")
    )
    if critical_action and action.requires_tool:
        has_success = any(result.status == "success" for result in tool_results)
        if not has_success:
            violations.append("critical_tool_action_without_success")

    report = AuthorityInvariantReport(
        pending_fields_from_state_after=list(state_after.pending_fields),
        useful_slots_accounted=not any(
            item.startswith("useful_slots_unaccounted") for item in violations
        ),
        critical_tool_success_required="critical_tool_action_without_success"
        not in violations,
        active_flow_preserved_for_global_faq="global_faq_dropped_active_flow"
        not in violations,
        violations=violations,
    )
    if violations:
        raise RuntimeError(f"authority invariant failed: {', '.join(violations)}")
    return report
