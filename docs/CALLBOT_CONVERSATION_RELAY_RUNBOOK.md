# Callbot ConversationRelay Runbook

## Endpoints

- TwiML: `POST /webhook/voice/conversationrelay/twiml`
- WebSocket: `WS /webhook/voice/conversationrelay/ws`
- Health: `GET /__health` and `GET /healthz`

The TwiML endpoint returns a `<Connect><ConversationRelay ... /></Connect>` response using `VOICE_WS_URL`.

## Event mapping

- `setup` -> normalized as voice "hola".
- `prompt` -> user transcript text.
- `dtmf` -> `media.dtmf`, supporting `1` and `2` for offered slots.
- `interrupt` and `error` are accepted as ConversationRelay metadata and should remain safe.

## Voice behavior

- Greeting references Clinica Madre Vedruna and Clinica Santa Isabel.
- Price, human request, urgent request and unsupported specialty transfer via `voice_transfer_call`.
- Slot offers are limited to two options.
- Confirmation still requires RPA create success.

## Local dry-run test

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8080
```

Then call `POST /clients/vedruna/chat` with `channel=voice` for no-call smoke tests.

## Production notes

- Twilio needs a public secure `wss://` URL.
- The provisional IP is not enough as final voice URL.
- HTTP webhook signature validation should be added before real production calls if not supplied by the hosting edge.
- Do not place Twilio secrets in code or docs.

