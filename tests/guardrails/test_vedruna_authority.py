from __future__ import annotations

from core.adapters.vedruna.copy_renderer import render_vedruna_reply
from core.conversation.actions import ConversationAction
from core.conversation.copy_renderer import render_conversation_reply
from core.conversation.policy import reconcile_tool_results
from core.conversation.state_manager import ConversationState
from core.llm.schemas import ToolResult
from core.nlu.schemas import NLUResult


def test_nlu_schema_still_forbids_visible_reply_text() -> None:
    assert not hasattr(NLUResult(), "reply_text")


def test_no_confirmation_template_without_successful_create_tool() -> None:
    state = ConversationState(conversation_id="guard-1", client_id="vedruna")
    action = ConversationAction(
        action_type="answer_information",
        reply_intent="rpa_failure",
        reply_key="vedruna_rpa_failure",
    )
    rendered = render_conversation_reply(action, state, "whatsapp")
    assert "Confirmamos tu cita" not in rendered.text


def test_confirmation_template_requires_explicit_success_payload() -> None:
    state = ConversationState(conversation_id="guard-2", client_id="vedruna")
    action = ConversationAction(
        action_type="answer_information",
        reply_intent="appointment_created",
        reply_key="vedruna_confirm_appointment",
    )
    rendered = render_vedruna_reply(
        action,
        state,
        "whatsapp",
        [
            ToolResult(
                name="rpa_create_appointment",
                status="success",
                user_safe_summary="ok",
                data={
                    "ok": True,
                    "appointment_id": "apt-1",
                    "start": "2026-07-08T16:00:00+02:00",
                    "clinic": "santa_isabel",
                },
            )
        ],
    )
    assert "Confirmamos tu cita" in rendered.text
    assert "Santa Isabel" in rendered.text


def test_confirmation_template_defends_against_missing_tool_result() -> None:
    state = ConversationState(conversation_id="guard-3", client_id="vedruna")
    action = ConversationAction(
        action_type="answer_information",
        reply_intent="appointment_created",
        reply_key="vedruna_confirm_appointment",
    )
    rendered = render_vedruna_reply(action, state, "whatsapp", [])
    assert "Confirmamos tu cita" not in rendered.text


def test_create_tool_failure_reconciles_to_safe_copy() -> None:
    action = ConversationAction(
        action_type="call_tool",
        reply_intent="create_appointment",
        reply_key="vedruna_creating_appointment",
        requires_tool=True,
        tool_name="rpa_create_appointment",
        metadata={"vedruna_flow": "create_appointment"},
    )
    reconciled = reconcile_tool_results(
        action,
        [
            ToolResult(
                name="rpa_create_appointment",
                status="failed",
                user_safe_summary="fail",
                internal_code="rpa_http_error",
            )
        ],
    )
    assert reconciled.reply_key == "vedruna_rpa_failure"
    assert reconciled.requires_tool is False


def test_successful_create_models_whatsapp_reminder_24h() -> None:
    action = ConversationAction(
        action_type="call_tool",
        reply_intent="create_appointment",
        reply_key="vedruna_creating_appointment",
        requires_tool=True,
        tool_name="rpa_create_appointment",
        metadata={"vedruna_flow": "create_appointment"},
    )
    reconciled = reconcile_tool_results(
        action,
        [
            ToolResult(
                name="rpa_create_appointment",
                status="success",
                user_safe_summary="ok",
                data={
                    "ok": True,
                    "appointment_id": "apt-1",
                    "start": "2026-07-08T16:00:00+02:00",
                    "clinic": "santa_isabel",
                },
            )
        ],
    )
    reminder = reconciled.state_updates["tool_state"]["reminder"]
    assert reconciled.reply_key == "vedruna_confirm_appointment"
    assert reminder["channel"] == "whatsapp"
    assert reminder["send_at"] == "2026-07-07T16:00:00+02:00"


def test_no_legacy_vertical_or_voice_errata_copy_in_vedruna_renderer() -> None:
    import inspect

    from core.adapters.vedruna import copy_renderer

    source = inspect.getsource(copy_renderer)
    lowered = source.lower()
    forbidden = ["pelu" + "quer", "sa" + "lon", "sarro" + "ca"]
    for term in forbidden:
        assert term not in lowered
