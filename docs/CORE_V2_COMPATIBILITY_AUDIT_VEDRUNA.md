# Core v2 Compatibility Audit - Vedruna

Scope: comparison against the Core v2 / Hybrid Router requirements supplied in the production prompt. `CoreChatbot_v2.odt` was not present in this repository during this pass.

## Summary

The current Vedruna repo remains production-oriented around the existing authority pipeline:

Inbound normalized -> NLU / structured interpretation -> StateReducer -> Policy Engine -> ToolExecutor -> CopyRenderer -> outbox/channel.

A thin Core v2 compatibility layer now exists through `HybridRoutingDecision` and trace mapping. It does not replace the current pipeline.

## Matrix

| Core v2 requirement | Current status | Current file | Minimal production action | Ideal later action |
| --- | --- | --- | --- | --- |
| ConversationRouter / Hybrid Router | partial | `core/router/hybrid.py`, `core/conversation/orchestrator.py` | Keep mapped `HybridRoutingDecision` in every authority trace. | Promote router to first-class pre-policy decision component. |
| HybridRoutingDecision | complies | `core/router/hybrid.py`, `core/conversation/contracts.py` | Monitor `hybridRoutingDecision.route`, `confidence`, `reason`, `result`. | Persist routing decisions in a dedicated analytics view. |
| Standard routes | partial | `core/router/hybrid.py` | Current mapped routes cover `continue_active_flow`, `deterministic_flow`, `rag_answer`, `tool_action`, `clarify`, `safe_response`, `human_handoff`, `out_of_scope`, `fallback`. | Make routes explicit inputs to policy instead of derived trace output. |
| ToolDispatcher / API | complies | `core/tools/executor.py`, `core/tools/registry.py` | Keep RPA and voice tools behind registry handlers. | Add typed per-tool input/output contracts. |
| Feature flags | partial | `core/config.py`, `.env.example` | Use `RPA_DRY_RUN`, `TWILIO_VALIDATE_SIGNATURE`, `VOICE_TRANSFER_ENABLED`, shadow flags. | Centralize runtime flag audit events and admin visibility. |
| Shadow mode | partial | `core/conversation/orchestrator.py`, `core/config.py` | Existing LLM shadow flags are safe; keep disabled unless intentionally tested. | Add route-level shadow comparison for Hybrid Router decisions. |
| Vertical adapter | complies | `core/adapters/vedruna/*` | Keep Vedruna domain logic isolated in adapter modules. | Extract adapter conformance tests shared with other verticals. |
| Confirmed slot protection | complies | `core/slots/merge.py`, `core/adapters/vedruna/nlu.py` | Selected slots now carry id, date, dateISO and time. | Add stronger immutable slot locks after confirmation. |
| Traceability of decision, confidence, route and result | complies | `core/conversation/contracts.py`, `core/router/hybrid.py` | Consume `authority_trace.hybridRoutingDecision`. | Add dashboard/reporting for route drift and low-confidence turns. |
| CopyRenderer as only visible copy source | complies | `core/conversation/copy_renderer.py`, `core/adapters/vedruna/copy_renderer.py` | Keep NLU structured-only and policy key-driven. | Add static checker for adapter render keys. |

## Production posture

Core v2 compatibility is partial but acceptable for controlled production preparation because the existing authority pipeline remains intact, guardrails are tested, and Hybrid Router semantics are traceable without a risky rewrite.
