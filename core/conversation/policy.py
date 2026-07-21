from __future__ import annotations

from datetime import datetime, timedelta

from core.adapters.vedruna import VEDRUNA_CLIENT_ID
from core.adapters.vedruna.policy import decide_vedruna_action
from core.conversation.actions import ConversationAction
from core.conversation.state_manager import ConversationState
from core.llm.schemas import ToolResult
from core.nlu.schemas import NLUResult
from core.tools.registry import ToolRegistry


def decide_next_action(
    context: ConversationState,
    nlu_result: NLUResult,
    registry: ToolRegistry | None = None,
) -> ConversationAction:
    if context.client_id == VEDRUNA_CLIENT_ID:
        return _anti_loop(
            decide_vedruna_action(context, nlu_result, registry),
            context,
            nlu_result,
        )
    del registry
    if "red_flag" in nlu_result.safety_signals:
        return _anti_loop(
            ConversationAction(
                action_type="red_flag_handoff",
                reply_intent="needs_human_review",
                reply_key="red_flag_visible_handoff",
                visible_handoff_required=True,
                requires_tool=True,
                tool_name="handoff_to_human",
                handoff_reason="safety_review",
                requires_human=True,
                target_role="human_team",
                safety_level="high",
            ),
            context,
            nlu_result,
        )
    if nlu_result.safety_signals:
        return _anti_loop(
            ConversationAction(
                action_type="handoff_visible",
                reply_intent="needs_human_review",
                reply_key="handoff_visible",
                visible_handoff_required=True,
                requires_tool=True,
                tool_name="handoff_to_human",
                handoff_reason="review_requested",
                requires_human=True,
                target_role="human_team",
                safety_level="medium",
            ),
            context,
            nlu_result,
        )
    if nlu_result.is_information_only:
        return _anti_loop(
            ConversationAction(
                action_type="cancel_flow",
                reply_intent="information_only",
                reply_key="information_only_ack",
                state_updates={
                    "information_only": True,
                    "current_flow": None,
                    "pending_action": None,
                },
            ),
            context,
            nlu_result,
        )
    if nlu_result.is_negative_appointment:
        return _anti_loop(
            ConversationAction(
                action_type="cancel_flow",
                reply_intent="cancel_flow",
                reply_key="cancel_flow_ack",
                state_updates={
                    "current_flow": None,
                    "pending_action": None,
                    "active_topic": None,
                },
            ),
            context,
            nlu_result,
        )
    if nlu_result.intent == "critical_change_request":
        return _anti_loop(
            ConversationAction(
                action_type="confirm_before_action",
                reply_intent="confirm_critical_change",
                reply_key="confirm_before_critical_action",
                requires_confirmation=True,
                safety_level="high",
                metadata={"critical_action": True},
            ),
            context,
            nlu_result,
        )
    if "human_requested" in nlu_result.signals:
        return _anti_loop(
            ConversationAction(
                action_type="handoff_visible",
                reply_intent="human_requested",
                reply_key="handoff_visible",
                visible_handoff_required=True,
                requires_tool=True,
                tool_name="handoff_to_human",
                requires_human=True,
                target_role="human_team",
            ),
            context,
            nlu_result,
        )
    if nlu_result.is_price_question:
        return _anti_loop(
            ConversationAction(
                action_type="answer_information",
                reply_intent="price_information",
                reply_key=_price_reply_key(context),
                target=context.current_flow or context.active_topic,
            ),
            context,
            nlu_result,
        )
    if "correction" in nlu_result.signals:
        return _anti_loop(
            ConversationAction(
                action_type="clarify_scope",
                reply_intent="acknowledge_correction",
                reply_key="correction_ack",
                target=context.current_flow or context.active_topic,
            ),
            context,
            nlu_result,
        )
    if context.client_id == "mudanzas_example":
        return _anti_loop(_mudanzas_action(context), context, nlu_result)
    if context.client_id == "somos_perros_example":
        return _anti_loop(_perros_action(context), context, nlu_result)
    if nlu_result.contextual_reply_to_last_question:
        return _anti_loop(
            ConversationAction(
                action_type="continue_existing_flow",
                reply_intent="continue_context",
                reply_key="continue_existing_flow",
                target=context.current_flow or context.active_topic,
            ),
            context,
            nlu_result,
        )
    return _anti_loop(
        ConversationAction(
            action_type="fallback_contextual",
            reply_intent="general_help",
            reply_key="fallback_contextual",
            target=context.current_flow or context.active_topic,
        ),
        context,
        nlu_result,
    )


def reconcile_tool_results(
    action: ConversationAction,
    tool_results: list[ToolResult],
) -> ConversationAction:
    if not tool_results:
        return action
    if action.metadata.get("vedruna_flow") or action.tool_name in {
        "rpa_search_availability",
        "rpa_create_appointment",
        "rpa_find_appointment",
        "rpa_cancel_appointment",
        "rpa_reschedule_appointment",
        "voice_transfer_call",
        "schedule_reminder",
    }:
        return _reconcile_vedruna_tool_results(action, tool_results)
    blocked = next((result for result in tool_results if result.status == "blocked"), None)
    if blocked:
        reply_key = (
            "tool_blocked_confirmation_required"
            if blocked.internal_code == "confirmation_required"
            else "tool_blocked_visible"
        )
        return action.model_copy(
            update={
                "action_type": "confirm_before_action"
                if blocked.internal_code == "confirmation_required"
                else "clarify_scope",
                "reply_intent": "tool_blocked",
                "reply_key": reply_key,
                "requires_tool": False,
                "tool_name": None,
                "requires_confirmation": blocked.internal_code == "confirmation_required",
                "metadata": {**action.metadata, "tool_status": blocked.status},
            }
        )
    failed = next((result for result in tool_results if result.status == "failed"), None)
    if failed:
        return action.model_copy(
            update={
                "action_type": "handoff_visible",
                "reply_intent": "tool_failed",
                "reply_key": "tool_failed_visible",
                "visible_handoff_required": True,
                "requires_tool": False,
                "tool_name": None,
                "requires_human": True,
                "metadata": {**action.metadata, "tool_status": failed.status},
            }
        )
    dry_run = next((result for result in tool_results if result.status == "dry_run"), None)
    if dry_run:
        return action.model_copy(
            update={
                "action_type": "fallback_contextual",
                "reply_intent": "tool_proposed_not_confirmed",
                "reply_key": "tool_dry_run_notice",
                "requires_tool": False,
                "tool_name": None,
                "metadata": {**action.metadata, "tool_status": dry_run.status},
            }
        )
    if action.tool_name == "handoff_to_human":
        return action.model_copy(
            update={
                "action_type": "handoff_visible",
                "reply_intent": "handoff_completed",
                "reply_key": "handoff_visible_success",
                "visible_handoff_required": True,
                "requires_tool": False,
                "tool_name": None,
                "requires_human": True,
                "state_updates": {**action.state_updates, "mode": "human"},
            }
        )
    return action.model_copy(
        update={
            "reply_key": "tool_success_visible",
            "metadata": {**action.metadata, "tool_status": "success"},
        }
    )


def _reconcile_vedruna_tool_results(
    action: ConversationAction,
    tool_results: list[ToolResult],
) -> ConversationAction:
    result = tool_results[-1]
    if result.status == "blocked" and result.internal_code == "confirmation_required":
        pending_action = {
            "tool_name": action.tool_name,
            "tool_arguments": action.tool_arguments,
            "reply_intent": action.reply_intent,
            "reply_key": action.reply_key,
            "handoff_reason": action.handoff_reason,
            "safety_level": action.safety_level,
            "metadata": action.metadata,
        }
        return action.model_copy(
            update={
                "action_type": "confirm_before_action",
                "reply_intent": "confirmation_required",
                "reply_key": "vedruna_confirmation_required",
                "requires_tool": False,
                "tool_name": None,
                "requires_confirmation": True,
                "state_updates": {
                    **action.state_updates,
                    "pending_action": pending_action,
                },
                "metadata": {**action.metadata, "tool_status": result.status},
            }
        )
    if result.status in {"blocked", "failed"}:
        return action.model_copy(
            update={
                "action_type": "answer_information",
                "reply_intent": "rpa_failure",
                "reply_key": "vedruna_rpa_failure",
                "requires_tool": False,
                "tool_name": None,
                "metadata": {**action.metadata, "tool_status": result.status},
            }
        )
    if result.status == "dry_run":
        reply_key = "vedruna_create_dry_run_notice"
        if action.tool_name in {"rpa_cancel_appointment", "rpa_reschedule_appointment"}:
            reply_key = "vedruna_rpa_failure"
        return action.model_copy(
            update={
                "action_type": "answer_information",
                "reply_intent": "dry_run_write_suppressed",
                "reply_key": reply_key,
                "requires_tool": False,
                "tool_name": None,
                "metadata": {**action.metadata, "tool_status": result.status},
            }
        )
    if action.tool_name == "rpa_search_availability":
        previous_tool_state = action.state_updates.get("tool_state", {})
        if not isinstance(previous_tool_state, dict):
            previous_tool_state = {}
        return action.model_copy(
            update={
                "action_type": "ask_missing_context",
                "reply_intent": "offer_slots",
                "reply_key": "vedruna_offer_slots",
                "requires_tool": False,
                "tool_name": None,
                "state_updates": {
                    **action.state_updates,
                    "tool_state": {
                        **previous_tool_state,
                        "last_offered_slots": list(result.data.get("slots", [])),
                        "last_tool_status": "success",
                    },
                    "pending_fields": ["selected_slot_id"],
                },
                "metadata": {**action.metadata, "tool_status": "success"},
            }
        )
    if action.tool_name == "rpa_create_appointment":
        if result.data.get("ok") is True and not result.data.get("dry_run"):
            return action.model_copy(
                update={
                    "action_type": "answer_information",
                    "reply_intent": "appointment_created",
                    "reply_key": "vedruna_confirm_appointment",
                    "requires_tool": False,
                    "tool_name": None,
                    "state_updates": {
                        **action.state_updates,
                        "current_flow": None,
                        "active_flow": None,
                        "active_topic": None,
                        "pending_fields": [],
                        "tool_state": {
                            "last_tool_status": "success",
                            "appointment_id": result.data.get("appointment_id"),
                            "reminder": result.data.get("reminder")
                            or _vedruna_reminder_plan(result.data),
                        },
                    },
                    "metadata": {**action.metadata, "tool_status": "success"},
                }
            )
        return action.model_copy(
            update={
                "action_type": "answer_information",
                "reply_intent": "rpa_failure",
                "reply_key": "vedruna_rpa_failure",
                "requires_tool": False,
                "tool_name": None,
            }
        )
    if action.tool_name == "rpa_find_appointment":
        reply_key = "vedruna_recall_result"
        if action.metadata.get("vedruna_flow") == "cancel_lookup":
            reply_key = "vedruna_cancel_confirm_prompt"
        elif action.metadata.get("vedruna_flow") == "reschedule_lookup":
            reply_key = "vedruna_reschedule_result"
        return action.model_copy(
            update={
                "action_type": "answer_information",
                "reply_intent": "appointment_lookup",
                "reply_key": reply_key,
                "requires_tool": False,
                "tool_name": None,
                "state_updates": {
                    **action.state_updates,
                    "tool_state": {
                        "last_lookup": result.data.get("appointment"),
                        "last_tool_status": "success",
                    },
                },
                "metadata": {**action.metadata, "tool_status": "success"},
            }
        )
    if action.tool_name == "rpa_cancel_appointment":
        if result.data.get("ok") is not True or result.data.get("dry_run") is True:
            return action.model_copy(
                update={
                    "action_type": "answer_information",
                    "reply_intent": "rpa_failure",
                    "reply_key": "vedruna_rpa_failure",
                    "requires_tool": False,
                    "tool_name": None,
                }
            )
        return action.model_copy(
            update={
                "action_type": "answer_information",
                "reply_intent": "appointment_cancelled",
                "reply_key": "vedruna_cancelled",
                "requires_tool": False,
                "tool_name": None,
                "state_updates": {
                    **action.state_updates,
                    "current_flow": None,
                    "active_flow": None,
                },
                "metadata": {**action.metadata, "tool_status": "success"},
            }
        )
    if action.tool_name == "rpa_reschedule_appointment":
        if result.data.get("ok") is not True or result.data.get("dry_run") is True:
            return action.model_copy(
                update={
                    "action_type": "answer_information",
                    "reply_intent": "rpa_failure",
                    "reply_key": "vedruna_rpa_failure",
                    "requires_tool": False,
                    "tool_name": None,
                }
            )
        return action.model_copy(
            update={
                "action_type": "answer_information",
                "reply_intent": "appointment_rescheduled",
                "reply_key": "vedruna_rescheduled",
                "requires_tool": False,
                "tool_name": None,
                "state_updates": {
                    **action.state_updates,
                    "current_flow": None,
                    "active_flow": None,
                },
                "metadata": {**action.metadata, "tool_status": "success"},
            }
        )
    if action.tool_name == "voice_transfer_call":
        return action.model_copy(
            update={
                "action_type": "handoff_visible",
                "reply_intent": "voice_transfer_started",
                "reply_key": "vedruna_voice_transfer",
                "requires_tool": False,
                "tool_name": None,
                "requires_human": True,
                "state_updates": {**action.state_updates, "mode": "human"},
                "metadata": {**action.metadata, "tool_status": "success"},
            }
        )
    return action.model_copy(
        update={
            "requires_tool": False,
            "tool_name": None,
            "metadata": {**action.metadata, "tool_status": "success"},
        }
    )


def _vedruna_reminder_plan(data: dict[str, object]) -> dict[str, object] | None:
    start = data.get("start")
    if not isinstance(start, str):
        return None
    try:
        parsed = datetime.fromisoformat(start)
    except ValueError:
        return None
    return {
        "send_at": (parsed - timedelta(hours=24)).isoformat(),
        "channel": "whatsapp",
        "template": "appointment_reminder_24h",
        "consent_prompt_required": False,
    }


def _mudanzas_action(context: ConversationState) -> ConversationAction:
    if "origin" not in context.collected_info:
        return ConversationAction(
            action_type="ask_missing_context",
            reply_intent="collect_quote_origin",
            reply_key="mudanzas_ask_origin",
            target="origin",
            state_updates={"current_flow": "quote_lead", "active_topic": "quote_lead"},
        )
    if "destination" not in context.collected_info:
        return ConversationAction(
            action_type="ask_missing_context",
            reply_intent="collect_quote_destination",
            reply_key="mudanzas_ask_destination",
            target="destination",
        )
    return ConversationAction(
        action_type="ask_missing_context",
        reply_intent="collect_quote_date",
        reply_key="mudanzas_ask_date",
        target="date",
    )


def _perros_action(context: ConversationState) -> ConversationAction:
    if "dates" not in context.collected_info:
        return ConversationAction(
            action_type="ask_missing_context",
            reply_intent="collect_reservation_dates",
            reply_key="perros_ask_dates",
            target="dates",
            state_updates={"current_flow": "reservation", "active_topic": "reservation"},
        )
    return ConversationAction(
        action_type="ask_missing_context",
        reply_intent="collect_pet_details",
        reply_key="perros_ask_pet_details",
        target="pet_details",
    )


def _price_reply_key(context: ConversationState) -> str:
    if context.client_id == "mudanzas_example":
        return "mudanzas_price_context"
    if context.client_id == "somos_perros_example":
        return "perros_price_context"
    return "price_contextual"


def _anti_loop(
    action: ConversationAction,
    context: ConversationState,
    nlu_result: NLUResult,
) -> ConversationAction:
    correction_or_pushback = (
        "correction" in nlu_result.signals
        or nlu_result.is_information_only
        or nlu_result.is_negative_appointment
    )
    recently_repeated = action.reply_key == context.last_reply_key and action.reply_key in (
        context.recent_reply_keys[-2:]
    )
    if recently_repeated and correction_or_pushback and not action.visible_handoff_required:
        return action.model_copy(
            update={
                "action_type": "clarify_scope",
                "reply_intent": "avoid_repeat_after_correction",
                "reply_key": f"{action.reply_key}_clarify",
                "metadata": {**action.metadata, "anti_loop": True},
            }
        )
    return action
