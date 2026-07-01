# EasyPanel Deploy Runbook

This repo is prepared for a future EasyPanel deploy. This run did not deploy.

## Source

- GitHub repo: `https://github.com/Pauovidi/vedruna-chatbot`
- Recommended branch: `codex/vedruna-from-core-rpa-twilio-v1`
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
TWILIO_VOICE_NUMBER=<number>
RPA_BASE_URL=http://vedruna-rpa:8080
RPA_API_KEY=<secret>
RPA_DRY_RUN=true
RPA_TIMEOUT_MS=12000
PII_MASKING_ENABLED=true
```

Set `RPA_DRY_RUN=false` only after the external RPA has been validated against a real or approved sandbox.

## Healthchecks

- `GET /healthz`
- `GET /__health`

Production should report durable persistence through Postgres.

## RPA networking

- Same EasyPanel network: prefer `http://vedruna-rpa:8080`.
- External RPA: use HTTPS and API auth.

## Preproduction checklist

- Domain final confirmed.
- `VOICE_WS_URL` uses `wss://`.
- Twilio credentials configured.
- Meta/WhatsApp credentials configured if real WhatsApp send is enabled later.
- RPA contract confirmed by the RPA owner.
- RPA idempotency confirmed.
- RPA dry-run disabled only after validation.
- No `.env` committed.
- `python -m pytest -q` green.

## Rollback

Repoint EasyPanel to the previous branch or image. Keep `RPA_DRY_RUN=true` if there is any doubt about writes.

