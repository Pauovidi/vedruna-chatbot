from __future__ import annotations

from core.adapters.vedruna.channels.voice_conversationrelay import (
    normalize_conversationrelay_event,
)
from core.adapters.vedruna.channels.whatsapp import normalize_whatsapp_payload


def test_whatsapp_payload_normalizes_to_vedruna_client() -> None:
    inbound = normalize_whatsapp_payload({"From": "whatsapp:+34600111222", "Body": "hola"})
    assert inbound.client_id == "vedruna"
    assert inbound.channel == "whatsapp"
    assert inbound.text == "hola"


def test_conversationrelay_dtmf_normalizes_media() -> None:
    inbound = normalize_conversationrelay_event(
        {"type": "dtmf", "digits": "2", "callSid": "c1"}
    )
    assert inbound.client_id == "vedruna"
    assert inbound.channel == "voice"
    assert inbound.media["dtmf"] == "2"
