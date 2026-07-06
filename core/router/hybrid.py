from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

HybridRoute = Literal[
    "continue_active_flow",
    "deterministic_flow",
    "rag_answer",
    "tool_action",
    "clarify",
    "safe_response",
    "human_handoff",
    "out_of_scope",
    "fallback",
]


class HybridRoutingDecision(BaseModel):
    route: HybridRoute
    confidence: float = Field(ge=0, le=1)
    reason: str
    result: str | None = None
    source: Literal["mapped_from_policy"] = "mapped_from_policy"


def map_policy_to_hybrid_decision(
    *,
    action_type: str | None,
    reply_intent: str | None,
    reply_key: str | None,
    nlu_intent: str | None,
    nlu_global_intent: str | None,
    tool_name: str | None = None,
) -> HybridRoutingDecision:
    route = _route_for(
        action_type=action_type,
        reply_intent=reply_intent,
        reply_key=reply_key,
        nlu_global_intent=nlu_global_intent,
        tool_name=tool_name,
    )
    confidence = 0.9 if route in {"tool_action", "human_handoff"} else 0.82
    if nlu_intent in {None, "unknown"}:
        confidence = min(confidence, 0.62)
    return HybridRoutingDecision(
        route=route,
        confidence=confidence,
        reason=reply_intent or nlu_global_intent or nlu_intent or "policy_mapped",
        result=reply_key,
    )


def _route_for(
    *,
    action_type: str | None,
    reply_intent: str | None,
    reply_key: str | None,
    nlu_global_intent: str | None,
    tool_name: str | None,
) -> HybridRoute:
    if action_type in {"handoff_visible", "red_flag_handoff", "no_reply_human_mode"}:
        return "human_handoff"
    if action_type in {"ask_missing_context", "clarify_scope", "confirm_before_action"}:
        return "clarify"
    if action_type == "continue_existing_flow":
        return "continue_active_flow"
    if action_type == "fallback_contextual":
        return "fallback"
    if action_type == "cancel_flow":
        return "safe_response"
    if tool_name or reply_key in {
        "vedruna_offer_slots",
        "vedruna_confirm_appointment",
        "vedruna_cancelled",
        "vedruna_rescheduled",
    }:
        return "tool_action"
    if nlu_global_intent == "faq":
        return "rag_answer"
    if reply_intent in {"price_query", "urgent_request", "unsupported_specialty"}:
        return "safe_response"
    if action_type == "answer_information":
        return "deterministic_flow"
    return "out_of_scope"
