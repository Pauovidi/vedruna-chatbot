from __future__ import annotations

from core.conversation.reply_guardrails import adapt_for_channel, validate_reply
from core.observability.redaction import redact_payload


def test_guardrails_block_tool_names_and_flags_in_reply() -> None:
    guarded = validate_reply(
        "Voy a ejecutar la tool confirm_cancellation con required_flags."
    )
    assert guarded.forbidden_claim_detected is True
    assert guarded.reason_code == "technical_tool_name_leak"
    assert "confirm_cancellation" not in guarded.text


def test_guardrails_block_unsourced_price() -> None:
    guarded = validate_reply("Eso cuesta 200 euros.")
    assert guarded.reason_code == "unsourced_price_claim"
    assert "200" not in guarded.text


def test_whatsapp_redaction_is_brief() -> None:
    reply = (
        "Hola. Puedo ayudarte con eso. Primero dime el origen. "
        "Luego vemos destino y fecha. Despues servicios extra."
    )
    adapted = adapt_for_channel(reply, "whatsapp")
    assert len(adapted) <= 360
    assert adapted.count("\n") <= 2


def test_redaction_removes_pii_and_secrets() -> None:
    payload = {
        "email": "persona@example.com",
        "phone": "+34 600 111 222",
        "api_key": "secret",
    }
    redacted = redact_payload(payload)
    assert redacted["email"] == "[redacted_email]"
    assert redacted["phone"] == "[redacted_phone]"
    assert redacted["api_key"] == "[redacted]"
