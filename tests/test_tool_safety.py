from __future__ import annotations

from core.conversation.actions import ConversationAction
from core.conversation.copy_renderer import render_conversation_reply
from core.conversation.policy import decide_next_action, reconcile_tool_results
from core.conversation.state_manager import ConversationState
from core.llm.schemas import ToolResult
from core.nlu.schemas import NLUResult


def test_blocked_tool_does_not_confirm_action() -> None:
    action = ConversationAction(
        action_type="call_tool",
        reply_intent="cancel_booking",
        reply_key="tool_success_visible",
        requires_tool=True,
        tool_name="confirm_cancellation",
        requires_confirmation=True,
        safety_level="high",
    )
    reconciled = reconcile_tool_results(
        action,
        [
            ToolResult(
                name="confirm_cancellation",
                status="blocked",
                user_safe_summary="Necesito confirmarlo.",
                internal_code="confirmation_required",
            )
        ],
    )
    rendered = render_conversation_reply(
        reconciled,
        ConversationState(conversation_id="tool-1"),
        "whatsapp",
    )
    assert reconciled.action_type == "confirm_before_action"
    assert "cancel" not in rendered.text.lower()
    assert "confirmacion" in rendered.text.lower()


def test_dry_run_tool_does_not_claim_real_confirmation() -> None:
    action = ConversationAction(
        action_type="call_tool",
        reply_intent="create_reservation",
        reply_key="tool_success_visible",
        requires_tool=True,
        tool_name="create_reservation_proposal_stub",
    )
    reconciled = reconcile_tool_results(
        action,
        [
            ToolResult(
                name="create_reservation_proposal_stub",
                status="dry_run",
                user_safe_summary="Propuesta registrada en prueba.",
            )
        ],
    )
    rendered = render_conversation_reply(
        reconciled,
        ConversationState(conversation_id="tool-2"),
        "whatsapp",
    )
    assert "confirmado" not in rendered.text.lower()
    assert "propuesta" in rendered.text.lower()


def test_handoff_success_generates_visible_notice() -> None:
    action = ConversationAction(
        action_type="call_tool",
        reply_intent="human_requested",
        reply_key="handoff_visible",
        requires_tool=True,
        tool_name="handoff_to_human",
        visible_handoff_required=True,
        requires_human=True,
    )
    reconciled = reconcile_tool_results(
        action,
        [
            ToolResult(
                name="handoff_to_human",
                status="success",
                user_safe_summary="Aviso enviado.",
            )
        ],
    )
    rendered = render_conversation_reply(
        reconciled,
        ConversationState(conversation_id="tool-3"),
        "whatsapp",
    )
    assert rendered.handoff_notice_sent is True
    assert "equipo" in rendered.text.lower()


def test_policy_handoff_visible_is_never_silent_or_internal() -> None:
    state = ConversationState(conversation_id="handoff-1")
    action = decide_next_action(
        state,
        NLUResult(intent="complaint", safety_signals=["complaint"]),
    )
    rendered = render_conversation_reply(action, state, "whatsapp")
    assert action.action_type == "handoff_visible"
    assert rendered.text
    assert "equipo" in rendered.text.lower()
    internal_terms = ["handoff", "manual review", "requires_manual_review"]
    assert all(term not in rendered.text.lower() for term in internal_terms)
