# Conversation Bypass Audit

## Current visible-copy surfaces

- `core/conversation/copy_renderer.py`: central dispatcher.
- `core/adapters/vedruna/copy_renderer.py`: Vedruna templates.
- `api/routers/vedruna.py`: returns the rendered reply from the orchestrator for dry-run webhook tests; it does not author domain copy.
- `core/conversation/policy.py`: creates `ConversationAction`; it does not write visible text.
- `core/adapters/vedruna/policy.py`: creates `ConversationAction`; it does not write visible text.

## Guardrails

- NLU schema forbids arbitrary visible reply fields.
- Vedruna NLU produces structure only: intent, slots, target slots, signals.
- RPA writes in `RPA_DRY_RUN=true` return `dry_run`, not `success`.
- `vedruna_confirm_appointment` is only selected by reconciliation when `rpa_create_appointment` returns `status=success`, `ok=true`, and `dry_run` is not true.
- Price replies route to phone copy only and tests forbid amounts.
- Voice price/human/urgent paths route through `voice_transfer_call`.

## Audit findings

- No final Vedruna renderer strings contain legacy vertical copy or the inherited voice-name errata.
- Existing core examples remain in `clients/*_example` and generic copy, but Vedruna requests branch by `client_id=vedruna`.
- `api/routers/vedruna.py` returns dry-run webhook responses for testing; real outbound WhatsApp is not enabled.

## Pending

- Once the external RPA is delivered, audit actual HTTP error payloads and verify no PII or secrets are surfaced.
- If a real Twilio signature validator is added, audit rejected webhooks for safe logging.
