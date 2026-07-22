# ElevenLabs Native Agent Runbook

## Purpose

Use an ElevenLabs native agent for natural Spanish conversation. The Vedruna
core remains the authority for appointment state, clinic rules, availability,
confirmation, and RPA operations.

Do not configure the agent as a Custom LLM when using this integration. The
legacy Custom LLM endpoint makes the core produce every spoken phrase, which
is intentionally deterministic and is not the desired voice experience.

## Safe deployment prerequisites

Keep these values in the service environment:

```text
ELEVENLABS_NATIVE_AGENT_ENABLED=true
ELEVENLABS_AGENT_API_KEY=<new-long-random-secret>
RPA_DRY_RUN=true
RPA_LIVE_READS_ENABLED=false
VOICE_TRANSFER_ENABLED=false
```

`ELEVENLABS_AGENT_API_KEY` is dedicated to the native-agent tool and must not
reuse the Custom LLM key. The endpoint is disabled unless the enablement flag
is explicitly true.

## Server tool

Create one server tool in ElevenLabs with this contract:

```text
POST https://<public-base-url>/v1/agent/turn
Authorization: Bearer <ELEVENLABS_AGENT_API_KEY>
Content-Type: application/json
```

Request body schema:

```json
{
  "conversation_id": "{{system__conversation_id}}",
  "utterance": "the patient's latest utterance",
  "call_sid": "optional call identifier"
}
```

The agent must call this tool after every patient turn that concerns an
appointment, cancellation, modification, prices, urgency, or transfer. The
agent must treat the response as authoritative and must never invent an
operation outcome.

The response contains no patient-facing copy. Important fields are:

- `next_step`: the allowed next action.
- `pending_fields`: information still required by the core.
- `offered_slots`: slots returned by the core, if any.
- `requires_explicit_confirmation`: true before create, cancel, or reschedule.
- `handoff_required`: true when the core requires a clinic contact.
- `rpa_mode`: `dry_run`, `live_read_only` or `live`.
- `tool_results`: server-side result only; do not call an action successful
  unless its status is `success` and the core says it is confirmed.

## Agent instructions

Use this as the operational part of the ElevenLabs system prompt. Adapt the
opening and voice style in the agent UI, but keep these rules unchanged.

```text
Hablas en espanol de Espana, con un tono cercano, breve y natural. Eres el
asistente de Clinica Madre Vedruna y Clinica Santa Isabel.

No repitas frases de espera ni leas listas innecesarias. Haz una pregunta cada
vez y reconoce brevemente lo que ya ha dicho la persona.

Para cualquier gestion de cita, precio, urgencia, cancelacion, modificacion,
consulta de cita o peticion de persona, llama primero a la herramienta
core_process_turn con las palabras literales mas recientes del paciente.

Obedece siempre `next_step`, `pending_fields`, `offered_slots`,
`requires_explicit_confirmation`, `handoff_required` y `rpa_mode`.

Pide siempre la clinica cuando no este clara. Madre Vedruna admite podologia y
Sanitas, Generali o particular. Santa Isabel trabaja solo de forma particular.
No des precios. No diagnostiques ni valores urgencias. Para precios, urgencias
o una persona, sigue la indicacion de traspaso o contacto que devuelva el core.

No digas que una cita esta creada, cancelada o modificada hasta que la
herramienta devuelva una operacion `success`. Cuando
`requires_explicit_confirmation` sea true, resume la gestion propuesta y pide
una confirmacion clara. No aceptes una confirmacion inventada ni la sustituyas
por la eleccion de un hueco.

Si `rpa_mode` es `dry_run`, explica que es una simulacion de prueba y que no
se ha escrito en el software clinico. Nunca prometas que se ha enviado un
WhatsApp, se ha realizado una llamada o se ha creado un recordatorio sin un
resultado `success` del core.
```

Name the server tool `core_process_turn` in the agent UI.

## Test sequence

1. Confirm that `/healthz` reports native-agent enabled, RPA dry run, and
   transfer disabled.
2. In ElevenLabs Preview, ask for a Santa Isabel ecografia appointment using
   synthetic details only.
3. Confirm that the agent speaks naturally while the tool returns pending
   fields and then offered slots.
4. Select a slot. The next tool result must require explicit confirmation.
5. Say a clear confirmation. The result must say `dry_run`; it must not claim
   a real appointment.
6. Start separate preview conversations for price, urgency, human handoff,
   Santa Isabel with Sanitas, cancellation, and reschedule.

Do not attach a public phone number or enable a live transfer while this test
sequence is incomplete.
