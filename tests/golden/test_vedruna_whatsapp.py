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
    assert "simuladas de prueba" in offered.reply_text

    selected = turn(orchestrator, "la primera", conversation_id=conversation_id)
    assert selected.reply_key == "vedruna_confirmation_required"
    assert selected.tool_results[0].status == "blocked"
    assert "Confirmamos tu cita" not in selected.reply_text
    confirmed = turn(
        orchestrator,
        "si confirmo",
        conversation_id=conversation_id,
        confirmed=True,
    )
    assert confirmed.reply_key == "vedruna_create_dry_run_notice"
    assert confirmed.tool_results[0].status == "dry_run"
    state = store.load_state(conversation_id, "vedruna")
    assert state.slots["selected_slot_id"] == "dry-madre_vedruna-1"
    assert state.slots["selected_slot_date"] == "07/07/2026"
    assert state.slots["selected_slot_time"] == "10:00"


def test_cancel_lookup_preserves_flow_and_dry_run_never_cancels_real_appointment() -> None:
    orchestrator, _store = make_vedruna_orchestrator()
    conversation_id = "v-cancel"

    first = turn(
        orchestrator,
        "quiero cancelar mi cita",
        conversation_id=conversation_id,
    )
    assert first.reply_key == "vedruna_ask_phone_for_lookup"
    lookup = turn(orchestrator, "600111222", conversation_id=conversation_id)
    assert lookup.reply_key == "vedruna_cancel_confirm_prompt"
    assert lookup.tool_results[0].name == "rpa_find_appointment"
    assert "simulado" in lookup.reply_text.lower()

    cancelled = turn(orchestrator, "si", conversation_id=conversation_id)
    assert cancelled.reply_key == "vedruna_confirmation_required"
    assert cancelled.tool_results[0].name == "rpa_cancel_appointment"
    assert cancelled.tool_results[0].status == "blocked"
    assert "cancelado correctamente" not in cancelled.reply_text.lower()
    confirmed = turn(
        orchestrator,
        "si confirmo",
        conversation_id=conversation_id,
        confirmed=True,
    )
    assert confirmed.tool_results[0].status == "dry_run"


def test_recall_lookup_dry_run_is_not_presented_as_real_appointment() -> None:
    orchestrator, _store = make_vedruna_orchestrator()
    conversation_id = "v-recall"

    turn(orchestrator, "cuando tenia la cita", conversation_id=conversation_id)
    result = turn(orchestrator, "600111222", conversation_id=conversation_id)

    assert result.reply_key == "vedruna_recall_result"
    assert result.tool_results[0].name == "rpa_find_appointment"
    assert result.tool_results[0].data["dry_run"] is True
    assert "consulta simulada" in result.reply_text.lower()
    assert "tienes una cita" not in result.reply_text.lower()


def test_reschedule_flow_dry_run_does_not_claim_real_modification() -> None:
    orchestrator, _store = make_vedruna_orchestrator()
    conversation_id = "v-reschedule"

    turn(orchestrator, "quiero modificar mi cita", conversation_id=conversation_id)
    lookup = turn(orchestrator, "600111222", conversation_id=conversation_id)
    assert lookup.reply_key == "vedruna_reschedule_result"
    assert "simulado" in lookup.reply_text.lower()

    offered = turn(orchestrator, "miercoles por la tarde", conversation_id=conversation_id)
    assert offered.reply_key == "vedruna_offer_slots"
    assert offered.tool_results[0].name == "rpa_search_availability"

    selected = turn(orchestrator, "la primera", conversation_id=conversation_id)
    assert selected.tool_results[0].name == "rpa_reschedule_appointment"
    assert selected.tool_results[0].status == "blocked"
    assert selected.reply_key == "vedruna_confirmation_required"
    assert "modificado correctamente" not in selected.reply_text.lower()
    confirmed = turn(
        orchestrator,
        "si confirmo",
        conversation_id=conversation_id,
        confirmed=True,
    )
    assert confirmed.tool_results[0].status == "dry_run"


def test_urgent_whatsapp_enters_safe_booking_flow_without_diagnosis() -> None:
    orchestrator, store = make_vedruna_orchestrator()
    result = turn(orchestrator, "es urgente, necesito cita")

    assert result.reply_key == "vedruna_urgent_whatsapp"
    assert "cita mas proxima" in result.reply_text.lower()
    assert "diagn" not in result.reply_text.lower()
    state = store.load_state("v-1", "vedruna")
    assert state.active_flow == "vedruna_appointment"
