# vedruna-chatbot

Chatbot y callbot para Clinica Madre Vedruna y Clinica Santa Isabel, inicializado desde el core `devestial-conversation-core-openai`.

El repo mantiene la arquitectura:

```text
Core chatbot -> adapter Vedruna -> domain schema -> KB -> policy -> tools RPA -> CopyRenderer -> canales
```

Regla absoluta:

```text
No hay confirmacion visible de cita sin rpa_create_appointment ok true.
```

En `RPA_DRY_RUN=true`, las consultas de disponibilidad usan fixtures seguros y las escrituras de cita/cancelacion/reagendado quedan suprimidas.

## Ejecutar local

```bash
python -m venv .venv
. .venv/Scripts/activate
python -m pip install -e ".[dev,postgres]"
copy .env.example .env
uvicorn api.main:app --reload --port 8080
```

Endpoints principales:

- `GET /healthz`
- `GET /__health`
- `POST /clients/vedruna/chat`
- `POST /webhook/whatsapp/vedruna`
- `POST /webhook/voice/conversationrelay/twiml`
- `WS /webhook/voice/conversationrelay/ws`

## Variables clave

```env
APP_ENV=development
PORT=8080
PUBLIC_BASE_URL=https://chatbot.example.com
VOICE_WS_URL=wss://chatbot.example.com/webhook/voice/conversationrelay/ws
OPENAI_API_KEY=
DATABASE_URL=
RPA_BASE_URL=http://vedruna-rpa:8080
RPA_API_KEY=
RPA_DRY_RUN=true
RPA_TIMEOUT_MS=12000
```

No commits de `.env` reales, secretos Twilio/OpenAI/RPA ni credenciales de clinica.

## Tests

```bash
python -m pytest -q
python -m core.testing.golden_runner
python -m core.testing.latency_smoke
python -m core.tools.check_conversation_authority
```

## Documentacion

- `docs/VEDRUNA_DOMAIN_SCHEMA.md`
- `docs/CONVERSATION_AUTHORITY_CONTRACT.md`
- `docs/CONVERSATION_BYPASS_AUDIT.md`
- `docs/RPA_APPOINTMENTS_CONTRACT_VEDRUNA.md`
- `docs/CALLBOT_CONVERSATION_RELAY_RUNBOOK.md`
- `docs/EASYPANEL_DEPLOY_RUNBOOK.md`
- `docs/CONVERSATION_LATENCY_RUNBOOK.md`
- `docs/GOLDEN_FLOWS_VEDRUNA.md`
- `docs/STATE_OF_TRUTH_VEDRUNA.md`

## Safety status

Este repo esta preparado para revision y futuro deploy, pero no despliega, no envia WhatsApps reales, no realiza llamadas reales y no escribe en el software real de la clinica por defecto.
