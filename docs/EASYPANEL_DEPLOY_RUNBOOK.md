# EasyPanel Deploy Runbook

This repo is prepared for a future EasyPanel deploy. This run did not deploy.

## Source

- GitHub repo: `https://github.com/Pauovidi/vedruna-chatbot`
- Recommended branch: `codex/vedruna-production-rpa-corev2-twilio-postgres-v1`
- Dockerfile port: `8080`

## Required environment

```env
APP_ENV=production
TZ=Europe/Madrid
PORT=8080
PUBLIC_BASE_URL=https://chatbot.<dominio-final>
VOICE_WS_URL=wss://chatbot.<dominio-final>/webhook/voice/conversationrelay/ws
DATABASE_URL=<postgres>
OPENAI_API_KEY=<secret>
OPENAI_MODEL=<model>
TWILIO_ACCOUNT_SID=<secret>
TWILIO_AUTH_TOKEN=<secret>
TWILIO_WHATSAPP_FROM=<number>
TWILIO_VALIDATE_SIGNATURE=true
TWILIO_WHATSAPP_REPLY_MODE=twiml
TWILIO_VOICE_NUMBER=<number>
CONVERSATION_RELAY_TTS_PROVIDER=ElevenLabs
CONVERSATION_RELAY_VOICE=<voice_id>
CONVERSATION_RELAY_LANGUAGE=es-ES
CONVERSATION_RELAY_TRANSCRIPTION_LANGUAGE=es-ES
CONVERSATION_RELAY_WELCOME_GREETING=Hola, soy el asistente de Clinica Madre Vedruna y Clinica Santa Isabel. En que puedo ayudarte?
ELEVENLABS_CUSTOM_LLM_API_KEY=<secret-shared-only-with-elevenlabs>
ELEVENLABS_REMOTE_NLU_ENABLED=false
VOICE_TRANSFER_ENABLED=false
RPA_BASE_URL=https://vedruna-rpa-rpa.ddxo6v.easypanel.host
RPA_API_KEY=<secret>
RPA_DRY_RUN=true
RPA_TIMEOUT_MS=12000
ADMIN_PANEL_API_KEY=<secret-if-admin-api-added>
PII_MASKING_ENABLED=true
```

Set `RPA_DRY_RUN=false` only after the external RPA has been validated against a real or approved sandbox.

## Healthchecks

- `GET /healthz`
- `GET /__health`

Production should report durable persistence through Postgres.

## RPA networking

- External RPA: use HTTPS and API auth.
- Health is `GET /health` and does not require auth.
- Authenticated endpoints are under `/appointments/...`.

## Preproduction checklist

- Domain final confirmed.
- `VOICE_WS_URL` uses `wss://`.
- Twilio credentials configured.
- ElevenLabs Custom LLM points to `https://<public-domain>/v1/chat/completions`.
- ElevenLabs sends `X-ElevenLabs-Conversation-ID` from `system__conversation_id`.
- `ELEVENLABS_CUSTOM_LLM_API_KEY` is stored only in EasyPanel and ElevenLabs secrets.
- Keep `ELEVENLABS_REMOTE_NLU_ENABLED=false` until the Custom LLM preview has
  passed its conversational test suite. When enabled, OpenAI is used only for
  structured NLU; visible copy remains owned by the CopyRenderer.
- `TWILIO_VALIDATE_SIGNATURE=true` only after webhook URL and token are correct.
- Meta/WhatsApp credentials configured if real WhatsApp send is enabled later.
- RPA contract confirmed by the RPA owner.
- RPA idempotency confirmed.
- RPA dry-run disabled only after validation.
- No `.env` committed.
- `python -m pytest -q` green.

## Rollback

Repoint EasyPanel to the previous branch or image. Keep `RPA_DRY_RUN=true` if there is any doubt about writes.
