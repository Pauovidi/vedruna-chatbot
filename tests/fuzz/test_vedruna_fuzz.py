from __future__ import annotations

import pytest

from tests.vedruna_helpers import make_vedruna_orchestrator, turn


@pytest.mark.parametrize(
    ("text", "expected_reply_key"),
    [
        ("quiero ir a la otra clinica", "vedruna_ask_clinic"),
        ("mejor por la tarde", "vedruna_ask_clinic"),
        ("no, era Catalana Occidente", "vedruna_faq_insurance"),
        ("era para Santa Isabel", "vedruna_ask_service_santa"),
        ("precio de quiropodia", "vedruna_price_ask_clinic"),
        ("con una persona", "vedruna_human_handoff"),
        ("quiero cancelar la de manana", "vedruna_ask_phone_for_lookup"),
        ("cuando tenia la cita", "vedruna_ask_phone_for_lookup"),
        ("soy de Sanitas", "vedruna_faq_insurance"),
        ("voy particular", "vedruna_faq_insurance"),
    ],
)
def test_vedruna_fuzz_phrases_stay_safe(text: str, expected_reply_key: str) -> None:
    orchestrator, _store = make_vedruna_orchestrator()
    result = turn(orchestrator, text, conversation_id=f"fuzz-{expected_reply_key}")
    assert result.reply_key == expected_reply_key
    assert "euros" not in result.reply_text.lower()
    assert "Sarro" + "ca" not in result.reply_text
