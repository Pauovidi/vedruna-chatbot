# Migrating A Legacy Bot To The Core

## 1. Audit Legacy Routers And Templates

Find every place that:

- builds visible copy.
- sends directly to a channel.
- calls CRM/ERP/Sheets/calendar.
- keeps local conversation state.
- handles fallback outside a policy.

Each finding must move into NLU, reducer, policy, tool, renderer, or outbox.

## 2. Map Flows To Reducer And Policy

- Flow state becomes `ConversationState`.
- Collected values become `slots`.
- Missing data becomes `pending_fields`.
- Corrections become slot merge events.
- Decisions become `ConversationAction`.

## 3. Convert Templates To CopyRenderer

Visible templates should be keyed by `reply_key`. They cannot call tools, branch flow, or send channel messages.

## 4. Encapsulate Channels As Outbox

Twilio, Meta, webchat, voice, and email route handlers should normalize inbound, call the core runtime, then send via Outbox or an Outbox-compatible adapter.

## 5. Encapsulate External Writes As Tools

Sheets, CRM, ERP, calendars, payments, and n8n workflows are tool handlers. Critical writes require policy authorization, confirmation, required flags, and success before copy can claim completion.

## 6. Write Golden Tests First

Before migration, write tests for:

- greeting.
- slot collection.
- out-of-order data.
- corrections.
- cancellation.
- FAQ inside flow.
- human handoff.
- blocked/ambiguous client.
- tool failure and dry-run.
- anti-loop.
- latency trace.
- provider timeout fallback.
- voice/callbot handoff.

## 7. Keep Production Safe

Use branch deploys or previews first. Do not replay inbound messages. Keep jobs dry-run by default. Validate health, migrations, and queue checks separately from channel sends.

## 8. Migrate Latency And Identity Carefully

- Replace duplicate directory lookups with a per-turn cache and a TTL directory cache.
- Map identity results to known, unknown, ambiguous, or blocked.
- Keep deterministic fast paths structured: they return `NLUResult` and still go through reducer, policy, renderer, and outbox.
- Treat provider timeout as fallback, not as permission to skip authority.
- Use `authority_turn_timing_completed` to classify the slowest stage before changing flags.

## Lessons From Somos Muy Perros

Rigid flows fail when NLU is active but not authoritative. Symptoms include repeated prompts after corrections, FAQ being swallowed by an active reservation flow, direct Twilio fallbacks, and scheduled jobs that are hard to validate safely.

The fix is not more one-off conditions. Migrate reservation-like flows to:

- pending-fields slot merge.
- global intent escape before domain flow.
- deterministic fallback when provider output fails.
- terms gate before critical confirmation.
- scheduled tasks with dedupe and dry-run.
- template previews that never send or enqueue.
- authority traces with timings and no PII.
- explicit human-mode return-to-bot command.
