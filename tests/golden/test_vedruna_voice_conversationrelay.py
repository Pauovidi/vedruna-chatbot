from __future__ import annotations

from core.adapters.vedruna.channels.voice_conversationrelay import (
    conversationrelay_text_message,
    normalize_conversationrelay_event,
)
from core.conversation.runtime import ConversationRuntimeAdapters, run_conversation_turn
from tests.vedruna_helpers import make_vedruna_orchestrator, turn


def test_conversationrelay_setup_uses_vedruna_voice_greeting() -> None:
    orchestrator, _store = make_vedruna_orchestrator()
    inbound = normalize_conversationrelay_event({"type": "setup", "callSid": "call-1"})
    result = run_conversation_turn(
        inbound,
        ConversationRuntimeAdapters(orchestrator=orchestrator),
    )
    assert result.reply_key == "vedruna_greeting"
    assert "Clinica Madre Vedruna" in result.reply_text
    assert "Sarro" + "ca" not in result.reply_text


def test_voice_price_with_clinic_transfers() -> None:
    orchestrator, _store = make_vedruna_orchestrator()
    result = turn(
        orchestrator,
        "precio en Santa Isabel",
        conversation_id="voice-price",
        channel="voice",
    )
    assert result.reply_key == "vedruna_voice_transfer"
    assert result.requires_human is True
    assert result.tool_results[0].name == "voice_transfer_call"
    assert result.tool_results[0].data["transfer_enabled"] is False
    assert "transferencia real" in result.reply_text.lower()


def test_voice_greeting_with_booking_request_asks_clinic() -> None:
    orchestrator, _store = make_vedruna_orchestrator()
    result = turn(
        orchestrator,
        "Hola, quiero pedir una cita",
        conversation_id="voice-greeting-booking",
        channel="voice",
    )
    assert result.reply_key == "vedruna_ask_clinic"
    assert "Madre Vedruna" in result.reply_text
    assert "Santa Isabel" in result.reply_text


def test_voice_santa_isabel_insurance_precedes_service_question() -> None:
    orchestrator, _store = make_vedruna_orchestrator()
    result = turn(
        orchestrator,
        "Quiero cita en Santa Isabel y tengo Sanitas",
        conversation_id="voice-santa-insurance",
        channel="voice",
    )
    assert result.reply_key == "vedruna_santa_isabel_particular_only"
    assert "particular" in result.reply_text.lower()


def test_voice_dtmf_selects_first_offered_slot() -> None:
    orchestrator, store = make_vedruna_orchestrator()
    conversation_id = "voice-dtmf"
    for text in [
        "quiero cita en Santa Isabel para quiropodia",
        "me llamo Ana Perez",
        "600111222",
        "dolor en un callo",
    ]:
        turn(orchestrator, text, conversation_id=conversation_id, channel="voice")
    offered = turn(
        orchestrator,
        "miercoles por la tarde",
        conversation_id=conversation_id,
        channel="voice",
    )
    assert offered.reply_key == "vedruna_offer_slots"

    inbound = normalize_conversationrelay_event(
        {"type": "dtmf", "digits": "1", "callSid": conversation_id}
    )
    result = run_conversation_turn(
        inbound,
        ConversationRuntimeAdapters(orchestrator=orchestrator),
    )
    assert result.reply_key == "vedruna_create_dry_run_notice"
    assert store.load_state(conversation_id, "vedruna").slots["selected_slot_id"].startswith(
        "dry-santa_isabel"
    )


def test_conversationrelay_text_message_shape() -> None:
    assert conversationrelay_text_message("hola") == '{"type": "text", "token": "hola"}'
