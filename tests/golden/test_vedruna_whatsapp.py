from __future__ import annotations

from datetime import datetime

import pytest

from core.adapters.vedruna.domain_schema import service_allowed
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
    assert "Catalana Occidente" in result.reply_text
    assert "Generali" not in result.reply_text


def test_madre_vedruna_accepts_catalana_occidente_but_not_generali() -> None:
    orchestrator, _store = make_vedruna_orchestrator()
    conversation_id = "v-catalana-occidente"

    turn(
        orchestrator,
        "quiero cita en Madre Vedruna para ecografia",
        conversation_id=conversation_id,
    )
    accepted = turn(
        orchestrator,
        "Catalana Occidente",
        conversation_id=conversation_id,
    )
    assert accepted.reply_key == "vedruna_ask_first_name"

    other_orchestrator, _store = make_vedruna_orchestrator()
    turn(
        other_orchestrator,
        "quiero cita en Madre Vedruna para ecografia",
        conversation_id="v-generali-rejected",
    )
    rejected = turn(
        other_orchestrator,
        "Generali",
        conversation_id="v-generali-rejected",
    )
    assert rejected.reply_key == "vedruna_ask_insurance"


@pytest.mark.parametrize(
    "service",
    [
        "podologia",
        "quiropodia",
        "estudio_biomecanico",
        "infiltracion",
        "ecografia",
        "otro_problema",
    ],
)
def test_both_clinics_allow_the_same_services(service: str) -> None:
    assert service_allowed("madre_vedruna", service)
    assert service_allowed("santa_isabel", service)


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


def test_price_query_waits_for_clinic_without_entering_booking_flow() -> None:
    orchestrator, _store = make_vedruna_orchestrator()
    conversation_id = "v-price-clinic"

    first = turn(
        orchestrator,
        "cuanto cuesta una infiltracion",
        conversation_id=conversation_id,
    )
    assert first.reply_key == "vedruna_price_ask_clinic"

    second = turn(orchestrator, "Santa Isabel", conversation_id=conversation_id)
    assert second.reply_key == "vedruna_price_with_clinic"
    assert "976582768" in second.reply_text
    assert "nombre" not in second.reply_text.lower()


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
    assert datetime.strptime(state.slots["selected_slot_date"], "%d/%m/%Y").weekday() == 1
    assert state.slots["selected_slot_time"] == "10:00"


def test_booking_does_not_offer_madre_vedruna_on_monday() -> None:
    orchestrator, _store = make_vedruna_orchestrator()
    conversation_id = "v-madre-closed-monday"
    for text in [
        "quiero cita en Madre Vedruna para podologia",
        "particular",
        "me llamo Ana Perez",
        "600111222",
        "dolor en una una",
    ]:
        turn(orchestrator, text, conversation_id=conversation_id)

    result = turn(orchestrator, "el lunes por la manana", conversation_id=conversation_id)

    assert result.reply_key == "vedruna_offer_slots"
    assert "no atendemos los lunes" in result.reply_text.lower()
    assert "martes, jueves y viernes" in result.reply_text.lower()
    assert "Opcion" not in result.reply_text


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


def test_reschedule_synonym_and_full_name_lookup_are_supported() -> None:
    orchestrator, _store = make_vedruna_orchestrator()
    conversation_id = "v-reschedule-by-name"

    first = turn(
        orchestrator,
        "quiero reprogramar una cita",
        conversation_id=conversation_id,
    )
    assert first.reply_key == "vedruna_ask_phone_for_lookup"
    assert "nombre y apellidos" in first.reply_text.lower()

    lookup = turn(
        orchestrator,
        "Lucas Prueba Automatizada",
        conversation_id=conversation_id,
    )

    assert lookup.reply_key == "vedruna_reschedule_result"
    assert lookup.tool_results[0].name == "rpa_find_appointment"
    assert lookup.tool_results[0].data["dry_run"] is True


def test_lookup_does_not_accept_a_single_name_as_unique_identity() -> None:
    orchestrator, _store = make_vedruna_orchestrator()
    conversation_id = "v-recall-single-name"

    turn(orchestrator, "cuando tenia la cita", conversation_id=conversation_id)
    result = turn(orchestrator, "Lucas", conversation_id=conversation_id)

    assert result.reply_key == "vedruna_ask_phone_for_lookup"
    assert result.tool_results == []


def test_urgent_whatsapp_enters_safe_booking_flow_without_diagnosis() -> None:
    orchestrator, store = make_vedruna_orchestrator()
    result = turn(orchestrator, "es urgente, necesito cita")

    assert result.reply_key == "vedruna_urgent_whatsapp"
    assert "cita mas proxima" in result.reply_text.lower()
    assert "diagn" not in result.reply_text.lower()
    state = store.load_state("v-1", "vedruna")
    assert state.active_flow == "vedruna_appointment"
