# Conversation Authority Contract

## Rule

No visible appointment confirmation may be sent without successful tool authority.

For Vedruna this means:

```text
rpa_create_appointment.status == success
rpa_create_appointment.data.ok == true
rpa_create_appointment.data.dry_run != true
```

Only then can the renderer use `vedruna_confirm_appointment`.

## Pipeline

All Vedruna channels enter the same chain:

```text
InboundNormalizer
-> NLU structured interpretation
-> StateReducer
-> Policy Engine
-> ToolExecutor
-> CopyRenderer
-> Outbox/channel response
-> AuthorityTurnTrace
```

## Responsibilities

- NLU: intent, slots, confidence and signals only. It cannot render final text.
- StateReducer: merges slots and records ignored/applied slots.
- Policy: decides next action, missing field, tool call or handoff.
- ToolExecutor: validates declared tools and runs handlers.
- RPA: source of truth for availability, create, find, cancel and reschedule.
- CopyRenderer: only visible user copy.
- Channel adapters: normalize inbound and deliver rendered copy without changing business rules.

## Vedruna guardrails

- Price questions never include amounts.
- Santa Isabel does not ask for insurance.
- Madre Vedruna asks Sanitas/Generali/particular.
- Runtime dry-run suppresses create/cancel/reschedule writes.
- Voice transfers for human, prices, urgent requests and unsupported specialty.
- WhatsApp urgent requests avoid diagnosis and recommend direct clinic contact for immediate care.
- Reminder scheduling is modeled after successful create; in dry-run it is not sent.

## Validation

- `tests/guardrails/test_vedruna_authority.py`
- `tests/golden/test_vedruna_whatsapp.py`
- `tests/golden/test_vedruna_voice_conversationrelay.py`
- `tests/fuzz/test_vedruna_fuzz.py`
- `tests/tools/test_rpa_appointments.py`

