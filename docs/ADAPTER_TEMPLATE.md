# Adapter Template

Use this checklist for every new client adapter.

## Files

- `business_profile.yaml`: public-safe business metadata and tone.
- `system_prompt.md`: client-specific NLU guidance, not final copy.
- `tools.yaml`: declarative tool contracts and risk/confirmation flags.
- `knowledge_seed.json`: sanitized source snippets.
- `golden_tests.yaml`: domain and cross-domain regression suite.

## Domain Model

Define:

- domain intents.
- domain slots.
- required pending fields.
- global intents that must escape active flow.
- critical actions and confirmation requirements.
- terms/contract requirements, if any.
- identity lookup states: known, unknown, ambiguous, blocked.
- latency smoke turns for the client channel.

## Reducer Extension

A reducer extension may:

- merge slots.
- update `pending_fields`.
- invalidate stale proposals.
- record applied/ignored slots.

It may not render copy, send messages, or execute tools.

## Policy Extension

A policy extension may:

- map state and NLU to `ConversationAction`.
- request a tool.
- require confirmation or terms acceptance.
- choose a `reply_key`.

It may not call external systems or create visible text.

## Copy Templates

Templates become renderer copy keyed by `reply_key`. They do not decide flow, call tools, or send directly.

## Channel Integration

WhatsApp, Twilio, Meta, voice, and webchat adapters must:

1. normalize inbound.
2. call `run_conversation_turn`.
3. send only the returned rendered/outbox message.

They may not build competing replies.

## Authority Trace And Latency

Adapters should preserve and expose only sanitized trace summaries:

- read `authority_trace` from `run_conversation_turn` for diagnostics.
- alert on high `totalDurationMs`, `nluProviderMs`, `persistenceMs`, or `eventLogMs`.
- keep identity/directory lookups cached per turn and by TTL where safe.
- never log raw bodies, phone numbers, tokens, or credentials.

## SMP-Derived Patterns To Include

- pending-fields slot targeting.
- out-of-order slot acceptance.
- correction handling.
- global FAQ/cancel/handoff escape.
- terms acceptance gate before critical confirmation.
- scheduled reminder/follow-up via dedupe queue.
- preview-only template rendering.
- human handoff and return-to-bot.
- deterministic fast path that still runs reducer, policy, renderer, and outbox.
- OpenAI timeout/fallback with `nlu_provider_timeout_fallback_used`.
