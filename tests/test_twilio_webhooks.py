from __future__ import annotations

import base64
import hashlib
import hmac

from fastapi.testclient import TestClient

import api.dependencies as dependencies
from api.main import create_app
from core.config import get_settings


def test_twilio_whatsapp_signature_off_allows_staging_webhook(monkeypatch) -> None:
    _reset_app_caches(monkeypatch)
    monkeypatch.setenv("TWILIO_VALIDATE_SIGNATURE", "false")

    response = TestClient(create_app()).post(
        "/webhook/whatsapp/vedruna",
        data={"Body": "hola", "From": "+34600111222"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    assert "<Response>" in response.text
    assert "<Message>" in response.text


def test_twilio_whatsapp_signature_valid_and_invalid_when_enabled(monkeypatch) -> None:
    _reset_app_caches(monkeypatch)
    monkeypatch.setenv("TWILIO_VALIDATE_SIGNATURE", "true")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token-test")
    client = TestClient(create_app())
    url = "http://testserver/webhook/whatsapp/vedruna"
    payload = {"Body": "hola", "From": "+34600111222"}
    signature = _twilio_signature(url, payload, "token-test")

    ok = client.post(
        "/webhook/whatsapp/vedruna",
        data=payload,
        headers={"X-Twilio-Signature": signature},
    )
    invalid = client.post(
        "/webhook/whatsapp/vedruna",
        data=payload,
        headers={"X-Twilio-Signature": "invalid"},
    )

    assert ok.status_code == 200
    assert invalid.status_code == 403


def test_conversationrelay_twiml_includes_wss_elevenlabs_and_voice(monkeypatch) -> None:
    _reset_app_caches(monkeypatch)
    monkeypatch.setenv("VOICE_WS_URL", "wss://voice.example/ws")
    monkeypatch.setenv("CONVERSATION_RELAY_TTS_PROVIDER", "ElevenLabs")
    monkeypatch.setenv("CONVERSATION_RELAY_VOICE", "voice-123")

    response = TestClient(create_app()).post("/webhook/voice/conversationrelay/twiml")

    assert response.status_code == 200
    assert 'url="wss://voice.example/ws"' in response.text
    assert 'ttsProvider="ElevenLabs"' in response.text
    assert 'voice="voice-123"' in response.text
    assert 'dtmfDetection="true"' in response.text


def _twilio_signature(url: str, payload: dict[str, str], token: str) -> str:
    signed = url + "".join(f"{key}{payload[key]}" for key in sorted(payload))
    digest = hmac.new(token.encode("utf-8"), signed.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("ascii")


def _reset_app_caches(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("RPA_DRY_RUN", "true")
    get_settings.cache_clear()
    dependencies.get_store.cache_clear()
    dependencies.get_events.cache_clear()
    dependencies.get_state_manager.cache_clear()
    dependencies.get_retriever.cache_clear()
    dependencies.get_registry.cache_clear()
    dependencies.get_orchestrator.cache_clear()
