from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TermsGateInput(BaseModel):
    terms_url: str | None = None
    terms_version: str | None = None
    terms_accepted: bool = False
    terms_accepted_at: datetime | None = None
    terms_source: str | None = None
    user_message: str = ""
    critical_action_requested: bool = False


class TermsGateResult(BaseModel):
    allowed: bool
    terms_accepted: bool
    requires_terms_link: bool = False
    terms_source: str | None = None
    reason: str


def evaluate_terms_gate(input_data: TermsGateInput) -> TermsGateResult:
    if not input_data.critical_action_requested:
        return TermsGateResult(
            allowed=True,
            terms_accepted=input_data.terms_accepted,
            terms_source=input_data.terms_source,
            reason="not_critical",
        )
    if input_data.terms_accepted:
        return TermsGateResult(
            allowed=True,
            terms_accepted=True,
            terms_source=input_data.terms_source,
            reason="terms_already_accepted",
        )
    normalized = input_data.user_message.lower().strip()
    if input_data.terms_url and normalized in {"acepto", "acepto las condiciones"}:
        return TermsGateResult(
            allowed=True,
            terms_accepted=True,
            terms_source="user_message",
            reason="accepted_after_terms_link",
        )
    return TermsGateResult(
        allowed=False,
        terms_accepted=False,
        requires_terms_link=bool(input_data.terms_url),
        reason="terms_required_before_critical_action",
    )
