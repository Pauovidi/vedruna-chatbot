from __future__ import annotations

from tests.vedruna_helpers import make_vedruna_orchestrator, turn


def test_whatsapp_asks_clinic_when_booking_is_ambiguous() -> None:
    orchestrator, _store = make_vedruna_orchestrator()
    result = turn(orchestrator, "quiero cita")
    assert result.reply_key == "vedruna_ask_clinic"
    assert "Madre Vedruna" in result.reply_text
    assert "Santa Isabel" in result.reply_text


def test_madre_vedruna_podologia_requires_insurance() -> None:
    orchestrator, _store = make_vedruna_orchestrator()
    result = turn(orchestrator, "quiero cita en Vedruna para podologia")
    assert result.reply_key == "vedruna_ask_insurance"
    assert "Sanitas" in result.reply_text
    assert "Generali" in result.reply_text


def test_santa_isabel_does_not_ask_insurance_for_quiropodia() -> None:
    orchestrator, _store = make_vedruna_orchestrator()
    result = turn(orchestrator, "quiero cita en Santa Isabel para quiropodia")
    assert result.reply_key == "vedruna_ask_first_name"
    assert "Sanitas" not in result.reply_text


def test_santa_isabel_insurance_mentions_particular_only() -> None:
    orchestrator, _store = make_vedruna_orchestrator()
    turn(orchestrator, "quiero cita en Santa Isabel para quiropodia")
    result = turn(orchestrator, "soy de Sanitas")
    assert result.reply_key == "vedruna_santa_isabel_particular_only"
    assert "particular" in result.reply_text.lower()


def test_price_query_never_returns_amount() -> None:
    orchestrator, _store = make_vedruna_orchestrator()
    result = turn(orchestrator, "precio de quiropodia en Santa Isabel")
    assert result.reply_key == "vedruna_price_with_clinic"
    assert "euros" not in result.reply_text.lower()
    assert "976582768" in result.reply_text


def test_full_booking_dry_run_offers_slots_but_does_not_confirm_real_appointment() -> None:
    orchestrator, store = make_vedruna_orchestrator()
    conversation_id = "v-full"
    for text in [
        "quiero cita",
        "Madre Vedruna",
        "podologia",
        "Sanitas",
        "me llamo Ana Perez",
        "600111222",
        "dolor en una una",
    ]:
        turn(orchestrator, text, conversation_id=conversation_id)
    offered = turn(orchestrator, "martes por la manana", conversation_id=conversation_id)
    assert offered.reply_key == "vedruna_offer_slots"
    assert offered.tool_results[0].name == "rpa_search_availability"
    assert offered.tool_results[0].status == "success"

    selected = turn(orchestrator, "la primera", conversation_id=conversation_id)
    assert selected.reply_key == "vedruna_create_dry_run_notice"
    assert selected.tool_results[0].status == "dry_run"
    assert "Confirmamos tu cita" not in selected.reply_text
    state = store.load_state(conversation_id, "vedruna")
    assert state.slots["selected_slot_id"] == "dry-madre_vedruna-1"
