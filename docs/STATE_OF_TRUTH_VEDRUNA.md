# State Of Truth - Vedruna / Santa Isabel

## Repo

- Destination repo: `https://github.com/Pauovidi/vedruna-chatbot`
- Working branch: `codex/vedruna-from-core-rpa-twilio-v1`
- Base copied from local core: `D:\PAU OVIDI MM\Documents\Core chatbot\devestial-conversation-core-openai`
- Core source HEAD observed before copy: `591ec82`

## Safety

- Deploy: not performed.
- WhatsApps reales enviados: no.
- Llamadas reales realizadas: no.
- Escrituras reales en RPA/software clinica: no.
- Secretos leidos/listados/impresos: no.
- `.env` reales: not copied.

## Implemented

- Vedruna client under `clients/vedruna`.
- Domain schema, KB, deterministic NLU, Policy, CopyRenderer.
- RPA client and handlers with dry-run default.
- WhatsApp normalizer and dry-run webhook.
- ConversationRelay TwiML and WebSocket scaffolding.
- Voice DTMF 1/2 slot selection.
- AuthorityTurnTrace remains from the core.
- Dockerfile and env example prepared for port 8080.

## Pending external inputs

- Final public domain for `PUBLIC_BASE_URL`.
- Final secure `VOICE_WS_URL`.
- Twilio credentials.
- OpenAI credentials.
- Real `RPA_BASE_URL`.
- Real `RPA_API_KEY`.
- Exact RPA contract from the RPA owner.
- Real clinic software sandbox or approved production process.
- EasyPanel service names.

## Business pending questions

1. Confirm final public domain and WSS URL.
2. Confirm EasyPanel service names for chatbot and RPA.
3. Confirm exact RPA contract.
4. Confirm whether RPA supports sandbox.
5. Confirm idempotency behavior.
6. Confirm whether RPA returns professional/agenda.
7. Confirm final urgent-request rule if WhatsApp and voice should be unified.
8. Confirm duration for ecografia.
9. Confirm duration for infiltracion or other problem.
10. Confirm default transfer number when clinic is unknown.
11. Confirm final legal/operational text for WhatsApp reminders.

