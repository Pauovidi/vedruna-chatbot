from __future__ import annotations

from typing import Any

from core.conversation.contracts import NormalizedInbound, StateReduction
from core.conversation.state_manager import ConversationState
from core.llm.schemas import IncomingMessage
from core.nlu.schemas import NLUResult
from core.slots import SlotMergeInput, merge_slots


def reduce_conversation_state(
    previous_context: ConversationState,
    nlu_result: NLUResult,
    user_message: IncomingMessage,
    previous_bot_action: dict[str, Any] | None,
) -> ConversationState:
    del previous_bot_action
    state = previous_context.model_copy(deep=True)
    state.client_id = user_message.client_id
    state.last_user_intent = nlu_result.intent
    state.active_flow = state.active_flow or state.current_flow
    state.channel_context = {
        **state.channel_context,
        "channel": user_message.channel,
        "last_user_reply_type": nlu_result.raw_user_reply_type,
        "language": nlu_result.language,
        "tone_hints": nlu_result.tone_hints,
    }
    state.price_question_pending = nlu_result.is_price_question

    if nlu_result.active_topic_hint:
        state.active_topic = nlu_result.active_topic_hint
        state.current_flow = nlu_result.active_topic_hint
        state.active_flow = nlu_result.active_topic_hint

    if nlu_result.is_information_only or nlu_result.is_negative_appointment:
        state.information_only = nlu_result.is_information_only
        state.current_flow = None
        state.active_flow = None
        state.pending_action = None
        state.pending_fields = []
        if nlu_result.is_negative_appointment:
            state.active_topic = None

    if "human_requested" in nlu_result.signals or nlu_result.safety_signals:
        state.handoff_pending = True

    _apply_entities(state, nlu_result)
    corrections = list(nlu_result.entities.get("correction_slot_names", []))
    if "correction" in nlu_result.signals:
        corrections.extend(nlu_result.slots)
    merged = merge_slots(
        SlotMergeInput(
            current_slots=state.slots,
            incoming_slots=nlu_result.slots,
            target_slots=nlu_result.target_slots,
            pending_fields=state.pending_fields,
            corrections=corrections,
            allow_out_of_order=True,
        )
    )
    state.slots = merged.slots
    state.pending_fields = merged.pending_fields
    state.audit["slot_merge"] = merged.model_dump(mode="json")
    return state


def _apply_entities(state: ConversationState, nlu_result: NLUResult) -> None:
    if "missing_items" in nlu_result.entities:
        state.collected_info["missing_items"] = nlu_result.entities["missing_items"]
        state.collected_info["correction_acknowledged"] = True
    if "correction" in nlu_result.signals:
        state.collected_info["last_correction"] = True


class CoreStateReducer:
    def reduce(
        self,
        state: ConversationState,
        inbound: NormalizedInbound,
        nlu_result: NLUResult,
    ) -> StateReduction:
        previous_slots = dict(state.slots)
        incoming = IncomingMessage(
            channel=inbound.channel,
            conversation_id=inbound.conversation_id,
            client_id=inbound.client_id,
            user_id=inbound.user_id,
            text=inbound.text,
            media=inbound.media,
            timestamp=inbound.timestamp,
        )
        reduced = reduce_conversation_state(state, nlu_result, incoming, state.pending_action)
        merge_payload = reduced.audit.get("slot_merge", {})
        applied = list(merge_payload.get("applied", [])) or [
            key
            for key, value in reduced.slots.items()
            if previous_slots.get(key) != value
        ]
        ignored = list(merge_payload.get("ignored", [])) or [
            key
            for key, value in nlu_result.slots.items()
            if value in (None, "") or reduced.slots.get(key) != value
        ]
        ignored_reasons = merge_payload.get("ignored_reasons", {})
        events: list[dict[str, Any]] = [
            {
                "event_type": "state_reduced",
                "payload": {
                    "intent": nlu_result.intent,
                    "active_flow": reduced.active_flow or reduced.current_flow,
                },
            },
            {
                "event_type": "slots_applied",
                "payload": {"slot_names": applied},
            },
        ]
        if ignored:
            events.append(
                {
                    "event_type": "slots_ignored",
                    "payload": {"slot_names": ignored},
                }
            )
        return StateReduction(
            state=reduced,
            events=events,
            applied_slots=applied,
            ignored_slots=ignored,
            pending_fields=list(reduced.pending_fields),
            ignored_slot_reasons=dict(ignored_reasons),
        )
