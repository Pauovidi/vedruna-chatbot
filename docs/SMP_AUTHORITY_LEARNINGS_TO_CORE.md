# SMP Authority Learnings To Core

Gap-check v2 against Somos Muy Perros authority and latency branches. SMP is a read-only reference; this core absorbs only generic patterns.

| SMP learning | Generic core pattern | Core destination | Gap found | Implementation status | Tests | Not copied |
| --- | --- | --- | --- | --- | --- | --- |
| NLU active is not enough if routers/templates send | Single authority runtime | `core/conversation/orchestrator.py` | Events existed but no final trace | Added `AuthorityTurnTrace` and anti-bypass checks | `test_authority_trace_and_state_after_timing_are_emitted` | Hotel route/templates |
| `state_after` governs policy/renderer | State reducer before policy and copy | `core/conversation/invariants.py` | No explicit invariant event | Added `state_after_invariants` | policy architecture tests | Reservation statuses |
| FAQ inside flow preserves state | Global intent escape | `core/policy/global_intents.py` | Event missing | Added `global_intent_escape` trace/event | core capability tests | Hotel FAQ taxonomy |
| Useful slots cannot disappear silently | Accounted slots with reasons | `core/slots/merge.py` | Ignored reasons missing | Added `ignored_reasons` | slot merge tests | Pet-specific fields |
| Partial time needs pendingFields targeting | `targetSlots=currentPending` | `core/slots/merge.py` | Basic merge only | Added family targeting | same-time slot test | Entry/exit hotel wording |
| Global escape hatch in any flow | cancel/FAQ/handoff/correction/red flag | `core/policy/global_intents.py` | Present, not traced | Trace event added | fuzz/golden | Hotel reset copy |
| One CopyRenderer | Renderer-owned visible text | `core/conversation/copy_renderer.py` | Present | Guarded by checker and trace | architecture tests | Product copy |
| One Outbox | Outbox-owned delivery | `core/outbox/base.py` | Present | Timed and traced | runtime/outbox test | Twilio send code |
| AuthorityTurnTrace with spans | Redacted per-turn trace | `core/conversation/contracts.py` | Missing | Added timing/count/flag model | trace/timing tests | Phone/user raw IDs |
| Latency avoids duplicate lookup/double NLU/heavy trace | stage timings and best-effort events | `core/conversation/orchestrator.py` | Missing | Added timing counters and deterministic fast path | latency smoke | SMP timing numbers |
| Fast path deterministic follows pipeline | Structured deterministic NLU before provider | `core/nlu/deterministic_interpreter.py` | No safe pre-provider path | Added safe global-intent fast path | timeout/trace tests | Hotel-specific intents |
| OpenAI timeout/fallback | Provider fallback to deterministic | `core/conversation/orchestrator.py` | Generic failure only | Added timeout event and `timedOutStage` | timeout test | Live OpenAI calls |
| Client identity cache/status | known/unknown/ambiguous/blocked | `core/identity/directory.py` | Missing module | Added memory directory with TTL cache | identity test | CLIENTES sheet schema |
| Scheduled messages | dedupe/status/dry-run queue | `core/scheduler/scheduled_tasks.py` | Present | Kept generic and checker-covered | scheduled test | Cron implementation |
| Template preview | Preview without actions/send | `core/templates/preview.py` | Present | Kept preview-only | preview test | WhatsApp templates |
| Terms/contract acceptance | Gate before critical action | `core/policy/terms.py` | Present | Documented in adapter/migration | terms test | Product contract URL |
| Human handoff mode | human mode suppression and return command | `core/conversation/orchestrator.py` | Return-to-bot missing | Added explicit return command | human return test | Panel controls |
| Guardrails/CI | repo-level bypass checker | `core/tools/check_conversation_authority.py` | Needed more forbidden fields | Added visible-field rules | checker test | Temporary legacy allowlists |

## Pending By Design

- Durable identity and scheduled task stores should be implemented by adapters before real production sends.
- Real channel adapters must provide an Outbox-compatible sender and keep dry-run tests.
- Latency numbers are environment-specific; the core records stage truth but does not promise product SLA.
