# Callbot ConversationRelay Runbook

## Endpoints

- TwiML: `POST /webhook/voice/conversationrelay/twiml`
- WebSocket: `WS /webhook/voice/conversationrelay/ws`
- Health: `GET /__health` and `GET /healthz`

The TwiML endpoint returns a `<Connect><ConversationRelay ... /></Connect>` response using `VOICE_WS_URL`. `VOICE_WS_URL` must be a public `wss://` URL.

## Event mapping

- `setup` -> normalized as voice "hola".
- `prompt` -> user transcript text.
- `dtmf` -> `media.dtmf`, supporting `1` and `2` for offered slots.
- `interrupt` and `error` are accepted as ConversationRelay metadata and should remain safe.

## Voice behavior

- Greeting references Clinica Madre Vedruna and Clinica Santa Isabel.
- Price, human request, urgent request and unsupported specialty transfer via `voice_transfer_call`.
- With `VOICE_TRANSFER_ENABLED=false`, the assistant does not claim that a real Twilio transfer happened.
- With `VOICE_TRANSFER_ENABLED=true`, the handler requires `CallSid`, Twilio credentials and a target clinic phone, then updates the active Twilio call through the REST API.
- Slot offers are limited to two options.
- Confirmation still requires RPA create success.

## ConversationRelay variables

```env
VOICE_WS_URL=wss://chatbot.<dominio-final>/webhook/voice/conversationrelay/ws
CONVERSATION_RELAY_TTS_PROVIDER=ElevenLabs
CONVERSATION_RELAY_VOICE=<voice_id>
CONVERSATION_RELAY_LANGUAGE=es-ES
CONVERSATION_RELAY_TRANSCRIPTION_LANGUAGE=es-ES
CONVERSATION_RELAY_WELCOME_GREETING=Hola, soy el asistente de Clinica Madre Vedruna y Clinica Santa Isabel. En que puedo ayudarte?
VOICE_TRANSFER_ENABLED=false
TWILIO_ACCOUNT_SID=<secret>
TWILIO_AUTH_TOKEN=<secret>
TWILIO_VOICE_NUMBER=<number>
```

## Local dry-run test

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8080
```

Then call `POST /clients/vedruna/chat` with `channel=voice` for no-call smoke tests.

## Production notes

- Twilio needs a public secure `wss://` URL.
- The provisional IP is not enough as final voice URL.
- Keep `VOICE_TRANSFER_ENABLED=false` until real transfer behavior is manually approved.
- Do not place Twilio secrets in code or docs.
