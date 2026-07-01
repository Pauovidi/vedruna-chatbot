# SMP Learnings To Core Capabilities

See `docs/SMP_AUTHORITY_LEARNINGS_TO_CORE.md` for the v2 gap-check with authority trace, latency, identity cache, and invariant coverage.

Read-only reference repo:
`D:/- TOT EL DEMES/TREBALLS/FEINA ACTUAL/Reddia/somos perros/Chatbot/hotel-canino-demo`

No product files were modified and no business data, URLs, phones, templates, Sheet IDs, or private configuration were copied.

## Mapping

| SMP learning | Generic core pattern | Core destination | Not copied | Generic tests |
| --- | --- | --- | --- | --- |
| Reservation flow slot targeting and pending fields | State-aware slot merge with corrections and out-of-order data | `core/slots/merge.py` | Hotel-specific dates, pet language, prices | slot merge unit tests and generic golden cases |
| Reset/FAQ/handoff winning inside active flow | Global intent escape hatch | `core/policy/global_intents.py` | Hotel FAQ taxonomy | global intent tests |
| Scheduled reminders and follow-ups | Dedupe scheduled task queue with dry-run dispatcher | `core/scheduler/scheduled_tasks.py` | Reminder wording and Twilio config | scheduler tests |
| Template preview route | Preview-only renderer with no enqueue/send/tool side effects | `core/templates/preview.py` | SMP templates and sample client data | preview tests |
| Contract acceptance before confirmation | Terms/contract gate for critical actions | `core/policy/terms.py` | Hotel terms copy or URLs | terms tests |
| Production job hardening | Base Python module pattern plus docs for jobs and checks | `docs/MIGRATING_LEGACY_BOT_TO_CORE.md` | Node scripts or deployment config | authority checker |
| Twilio route defensive fallback | Channel adapter must normalize inbound and use Outbox | `core/outbox/base.py` and docs | Twilio credentials and route code | outbox/runtime tests |
| Human mode suppression | Generic bot/human state with visible handoff before suppression | `ConversationState.mode` and policy tests | Panel-specific controls | handoff tests |
| Client directory identity states | Generic known/unknown/ambiguous/blocked status | `ConversationState.client_status` | Client records or pet data | state tests |

## Design Notes

The core absorbs capabilities, not vertical logic. Future adapters may add domain reducers and policies, but they must return core `ConversationAction` objects and let `CopyRenderer` and Outbox remain the only visible output path.
