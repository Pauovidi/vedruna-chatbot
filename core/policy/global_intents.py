from __future__ import annotations

from pydantic import BaseModel

from core.nlu.schemas import NLUResult


class GlobalIntentDecision(BaseModel):
    intent: str | None = None
    should_escape_active_flow: bool = False
    reason: str | None = None


ESCAPE_INTENTS = {
    "cancel_flow",
    "faq",
    "handoff",
    "reset",
    "correction",
    "media",
    "stop",
    "red_flag",
}


def resolve_global_intent(nlu_result: NLUResult) -> GlobalIntentDecision:
    intent = nlu_result.global_intent
    if intent in ESCAPE_INTENTS:
        return GlobalIntentDecision(
            intent=intent,
            should_escape_active_flow=True,
            reason="global_intent_precedes_domain_flow",
        )
    return GlobalIntentDecision(intent=intent)
