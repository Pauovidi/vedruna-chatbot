from __future__ import annotations

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter
from typing import Any
from uuid import uuid4

from core.config import Settings
from core.conversation.contracts import (
    AuthorityTurnTiming,
    AuthorityTurnTrace,
    IgnoredSlotTrace,
    StatePatchSummary,
)
from core.conversation.copy_renderer import render_conversation_reply
from core.conversation.invariants import enforce_authority_invariants
from core.conversation.memory import compact_context
from core.conversation.policy import decide_next_action, reconcile_tool_results
from core.conversation.state_manager import ConversationState, StateManager
from core.conversation.state_reducer import reduce_conversation_state
from core.knowledge.retriever import SimpleKnowledgeRetriever
from core.knowledge.schemas import KnowledgeSnippet
from core.llm.schemas import ChatTurnResult, IncomingMessage, ToolCallRequest
from core.nlu.deterministic_interpreter import DeterministicNLUInterpreter
from core.nlu.schemas import NLUInterpreter, NLUResult
from core.observability.events import EventRecorder
from core.outbox import MemoryOutbox, Outbox, OutboxMessage
from core.policy.global_intents import resolve_global_intent
from core.router.hybrid import map_policy_to_hybrid_decision
from core.tools.executor import ToolExecutor
from core.tools.registry import ToolRegistry
from core.tools.schemas import ToolDefinition, ToolHandler


class ConversationOrchestrator:
    def __init__(
        self,
        llm: NLUInterpreter,
        state_manager: StateManager,
        retriever: SimpleKnowledgeRetriever,
        registry: ToolRegistry,
        events: EventRecorder,
        settings: Settings | None = None,
        outbox: Outbox | None = None,
        tool_handlers: dict[str, ToolHandler] | None = None,
    ) -> None:
        self.nlu = llm
        self.settings = settings or getattr(llm, "settings", Settings())
        self.deterministic_nlu = DeterministicNLUInterpreter()
        self.state_manager = state_manager
        self.retriever = retriever
        self.registry = registry
        self.events = events
        self.executor = ToolExecutor(registry, events, handlers=tool_handlers)
        self.outbox = outbox or MemoryOutbox(dry_run=True)
        self._trace_events_written = 0
        self._trace_event_log_ms = 0.0
        self._trace_best_effort = False

    def handle_turn(self, message: IncomingMessage) -> ChatTurnResult:
        self._begin_trace_counters()
        turn_started = perf_counter()
        turn_id = f"turn_{uuid4().hex}"
        timings: dict[str, float] = {}
        counts = {"store_reads": 0, "store_writes": 0, "openai_calls": 0}
        nlu_metrics: dict[str, Any] = {
            "nlu_provider_used": "skipped",
            "used_openai": False,
            "used_fallback": False,
            "timed_out_stage": None,
            "nlu_provider_ms": 0,
            "deterministic_parser_ms": 0,
            "openai_calls": 0,
        }
        tool_results = []
        rendered = None
        action = None
        nlu_result: NLUResult | None = None
        applied_slots: list[str] = []
        ignored_slot_reasons: dict[str, str] = {}
        source_ids: list[str] = []
        state_before = ConversationState(conversation_id=message.conversation_id)
        state = state_before
        outbox_kind: str = "suppressed"
        loop_prevented = False
        policy_tool_name: str | None = None

        message = self._normalize_inbound(message)
        self._record_event(
            message.conversation_id,
            "authority_turn_started",
            {
                "turn_id": turn_id,
                "channel": message.channel,
                "has_text": bool(message.text),
                "has_media": bool(message.media),
            },
        )
        self._record_event(
            message.conversation_id,
            "inbound_normalized",
            {
                "channel": message.channel,
                "client_id": message.client_id,
                "has_text": bool(message.text),
                "has_media": bool(message.media),
            },
        )
        with _measure(timings, "persistence_ms"):
            self.state_manager.append_message(
                message.conversation_id,
                "user",
                message.text,
                client_id=message.client_id,
                channel=message.channel,
            )
            counts["store_writes"] += 1

        with _measure(timings, "load_state_ms"):
            state = self.state_manager.load(message.conversation_id, message.client_id)
            counts["store_reads"] += 1
            previous_messages = self.state_manager.list_messages(
                message.conversation_id,
                limit=8,
            )
            counts["store_reads"] += 1
        state.recent_context_summary = compact_context(previous_messages)
        state_before = state.model_copy(deep=True)

        if state.mode == "human" and not _is_return_to_bot_command(message.text):
            self._record_event(message.conversation_id, "human_mode_suppressed", {})
            trace = self._build_trace(
                turn_id=turn_id,
                message=message,
                turn_started=turn_started,
                timings=timings,
                counts=counts,
                nlu_metrics=nlu_metrics,
                state_before=state_before,
                state_after=state,
                nlu_result=None,
                applied_slots=[],
                ignored_slot_reasons={},
                action_type="no_reply_human_mode",
                policy_reason="human_mode_suppressed",
                policy_tool_name=None,
                render_key="human_mode_suppressed",
                outbox_kind="suppressed",
                loop_prevented=False,
            )
            self._record_trace(message.conversation_id, trace)
            return ChatTurnResult(
                conversation_id=message.conversation_id,
                reply_text="",
                requires_human=True,
                mode="human",
                action_type="no_reply_human_mode",
                reply_key="human_mode_suppressed",
                authority_trace=trace.model_dump(by_alias=True, mode="json"),
            )
        if state.mode == "human":
            state.mode = "bot"
            state.handoff_pending = False
            self._record_event(message.conversation_id, "human_mode_returned_to_bot", {})

        snippets = self.retriever.search_knowledge(
            message.text,
            client_id=message.client_id,
            top_k=3,
        )
        source_ids = [snippet.source_id for snippet in snippets]
        self._record_event(
            message.conversation_id,
            "nlu_called",
            {
                "provider": "openai" if self.settings.openai_api_key else "deterministic",
                "shadow": self.settings.conversational_reply_shadow,
            },
        )
        with _measure(timings, "nlu_total_ms"):
            nlu_result, nlu_metrics = self._interpret(
                message,
                state.model_dump(mode="json"),
                snippets,
            )
        counts["openai_calls"] += int(nlu_metrics.get("openai_calls", 0))
        self._record_event(
            message.conversation_id,
            "nlu_result",
            {
                "intent": nlu_result.intent,
                "confidence": nlu_result.confidence,
                "signals": nlu_result.signals,
                "safety_signals": nlu_result.safety_signals,
            },
        )
        self._record_event(
            message.conversation_id,
            "nlu_result_received",
            {
                "intent": nlu_result.intent,
                "global_intent": nlu_result.global_intent,
                "domain_intent": nlu_result.domain_intent,
                "slot_names": list(nlu_result.slots),
            },
        )
        self._record_event(
            message.conversation_id,
            "nlu_slots_extracted",
            {
                "slot_names": list(nlu_result.slots),
                "target_slot_names": list(nlu_result.target_slots),
            },
        )
        global_decision = resolve_global_intent(nlu_result)
        if global_decision.should_escape_active_flow:
            self._record_event(
                message.conversation_id,
                "global_intent_escape",
                global_decision.model_dump(mode="json"),
            )

        with _measure(timings, "reducer_ms"):
            state = reduce_conversation_state(
                state,
                nlu_result,
                message,
                state.pending_action,
            )
        slot_merge = state.audit.get("slot_merge", {})
        applied_slots = list(slot_merge.get("applied", []))
        ignored_slot_reasons = dict(slot_merge.get("ignored_reasons", {}))
        self._record_event(
            message.conversation_id,
            "state_reduced",
            {
                "active_flow": state.active_flow or state.current_flow,
                "mode": state.mode,
            },
        )
        self._record_event(
            message.conversation_id,
            "state_reducer_applied",
            {
                "active_flow": state.active_flow or state.current_flow,
                "applied_slots": applied_slots,
                "ignored_slots": list(ignored_slot_reasons),
            },
        )
        self._record_event(
            message.conversation_id,
            "pending_fields_after_merge",
            {"pending_fields": list(state.pending_fields)},
        )
        if nlu_result.slots:
            self._record_event(
                message.conversation_id,
                "slots_applied",
                {"slot_names": applied_slots},
            )
            self._record_event(
                message.conversation_id,
                "nlu_slots_applied",
                {"slot_names": applied_slots},
            )
            ignored_slots = list(ignored_slot_reasons)
            if ignored_slots:
                self._record_event(
                    message.conversation_id,
                    "slots_ignored",
                    {"slot_names": ignored_slots, "reasons": ignored_slot_reasons},
                )
                self._record_event(
                    message.conversation_id,
                    "nlu_slots_ignored",
                    {"slot_names": ignored_slots, "reasons": ignored_slot_reasons},
                )

        with _measure(timings, "policy_ms"):
            action = decide_next_action(state, nlu_result, self.registry)
        self._record_event(
            message.conversation_id,
            "policy_action",
            {
                "action_type": action.action_type,
                "reply_key": action.reply_key,
                "requires_tool": action.requires_tool,
                "tool_name": action.tool_name,
            },
        )
        self._record_event(
            message.conversation_id,
            "policy_decision",
            {
                "action_type": action.action_type,
                "reply_key": action.reply_key,
                "requires_tool": action.requires_tool,
            },
        )
        loop_prevented = bool(action.metadata.get("anti_loop"))
        if loop_prevented:
            self._record_event(
                message.conversation_id,
                "loop_prevented",
                {"reply_key": action.reply_key},
            )

        policy_tool_name = action.tool_name
        if action.requires_tool and action.tool_name:
            with _measure(timings, "tools_ms"):
                tool_results.append(
                    self.executor.execute(
                        ToolCallRequest(
                            name=action.tool_name,
                            arguments=action.tool_arguments,
                            reason=action.handoff_reason or action.reply_intent,
                            requires_confirmation=action.requires_confirmation,
                            risk_level=action.safety_level,
                        ),
                        message,
                        confirmed=bool(message.media.get("confirmed")),
                        flags=state.flags,
                    )
                )
                action = reconcile_tool_results(action, tool_results)
            self._record_event(
                message.conversation_id,
                "post_tool_policy_action",
                {
                    "action_type": action.action_type,
                    "reply_key": action.reply_key,
                    "tool_statuses": [result.status for result in tool_results],
                },
            )

        for key, value in action.state_updates.items():
            if hasattr(state, key):
                setattr(state, key, value)
        if action.requires_human:
            state.handoff_pending = True

        invariant_report = enforce_authority_invariants(
            state_before=state_before,
            state_after=state,
            nlu_result=nlu_result,
            action=action,
            applied_slots=applied_slots,
            ignored_slot_reasons=ignored_slot_reasons,
            tool_results=tool_results,
        )
        self._record_event(
            message.conversation_id,
            "state_after_invariants",
            invariant_report.model_dump(mode="json"),
        )

        with _measure(timings, "renderer_ms"):
            rendered = render_conversation_reply(
                action,
                state,
                message.channel,
                tool_results,
            )
        self._record_event(
            message.conversation_id,
            "rendered_reply",
            rendered.model_dump(mode="json"),
        )
        self._record_event(
            message.conversation_id,
            "copy_rendered",
            rendered.model_dump(mode="json"),
        )
        self._record_event(
            message.conversation_id,
            "renderer_used",
            {"reply_key": rendered.reply_key, "visibility": rendered.visibility},
        )
        if rendered.text:
            with _measure(timings, "outbox_ms"):
                outbox_result = self.outbox.send(
                    OutboxMessage(
                        conversation_id=message.conversation_id,
                        channel=message.channel,
                        text=rendered.text,
                        reply_key=rendered.reply_key,
                        action_type=action.action_type,
                    )
                )
            outbox_kind = (
                "dry_run" if outbox_result.status == "dry_run" else "outbox_send"
            )
            self._record_event(
                message.conversation_id,
                "outbox_sent",
                outbox_result.model_dump(mode="json"),
            )
            with _measure(timings, "persistence_ms"):
                self.state_manager.append_message(
                    message.conversation_id,
                    "assistant",
                    rendered.text,
                    client_id=message.client_id,
                    channel=message.channel,
                    metadata={"reply_key": rendered.reply_key},
                )
                counts["store_writes"] += 1
        state.last_bot_question = rendered.text or state.last_bot_question
        state.last_assistant_question = rendered.text or state.last_assistant_question
        state.last_bot_action = action.action_type
        state.last_reply_key = rendered.reply_key
        state.recent_reply_keys = [*state.recent_reply_keys, rendered.reply_key][-6:]
        if rendered.handoff_notice_sent:
            state.handoff_visible_sent = True
        if action.state_updates.get("mode") == "human":
            state.mode = "human"
        with _measure(timings, "persistence_ms"):
            self.state_manager.save(state)
            counts["store_writes"] += 1

        self._record_event(
            message.conversation_id,
            "turn_completed",
            {
                "intent": nlu_result.intent,
                "action_type": action.action_type,
                "reply_key": rendered.reply_key,
                "source_ids": source_ids,
                "tool_results": [result.model_dump(mode="json") for result in tool_results],
            },
        )
        trace = self._build_trace(
            turn_id=turn_id,
            message=message,
            turn_started=turn_started,
            timings=timings,
            counts=counts,
            nlu_metrics=nlu_metrics,
            state_before=state_before,
            state_after=state,
            nlu_result=nlu_result,
            applied_slots=applied_slots,
            ignored_slot_reasons=ignored_slot_reasons,
            action_type=action.action_type,
            policy_reason=action.reply_intent,
            policy_tool_name=policy_tool_name,
            render_key=rendered.reply_key,
            outbox_kind=outbox_kind,
            loop_prevented=loop_prevented,
        )
        self._record_trace(message.conversation_id, trace)
        return ChatTurnResult(
            conversation_id=message.conversation_id,
            reply_text=rendered.text,
            requires_human=action.requires_human,
            priority=action.safety_level in {"high", "critical"},
            source_ids=source_ids,
            tool_results=tool_results,
            mode=state.mode,
            intent=nlu_result.intent,
            action_type=action.action_type,
            reply_key=rendered.reply_key,
            authority_trace=trace.model_dump(by_alias=True, mode="json"),
        )

    def _interpret(
        self,
        message: IncomingMessage,
        context: dict[str, object],
        snippets: list[KnowledgeSnippet],
    ) -> tuple[NLUResult, dict[str, Any]]:
        tools = self.registry.list()
        metrics: dict[str, Any] = {
            "nlu_provider_used": "deterministic",
            "used_openai": False,
            "used_fallback": False,
            "timed_out_stage": None,
            "nlu_provider_ms": 0,
            "deterministic_parser_ms": 0,
            "openai_calls": 0,
        }
        started = perf_counter()
        deterministic_result = self.deterministic_nlu.interpret(
            message,
            context,
            snippets,
            tools,
        )
        metrics["deterministic_parser_ms"] = _elapsed_ms(started)

        if self._can_use_deterministic_fast_path(deterministic_result):
            self._record_event(
                message.conversation_id,
                "nlu_deterministic_fast_path_used",
                {
                    "intent": deterministic_result.intent,
                    "global_intent": deterministic_result.global_intent,
                },
            )
            return deterministic_result, metrics

        if message.media.get("source") == "elevenlabs_custom_llm":
            # ElevenLabs has a short end-to-end custom-LLM deadline. This channel
            # already enters through a structured Vedruna interpreter, so avoid a
            # second remote NLU round trip and preserve the core policy pipeline.
            self._record_event(
                message.conversation_id,
                "nlu_elevenlabs_deterministic_fast_path_used",
                {
                    "intent": deterministic_result.intent,
                    "global_intent": deterministic_result.global_intent,
                },
            )
            return deterministic_result, metrics

        if not self.settings.conversational_reply_enabled:
            self._record_event(message.conversation_id, "llm_disabled", {})
            return deterministic_result, metrics

        if self.settings.conversational_reply_shadow:
            self._record_event(message.conversation_id, "llm_shadow_primary_deterministic", {})
            if (
                self.settings.conversational_reply_shadow_call_enabled
                and self.settings.openai_api_key
            ):
                metrics["openai_calls"] = 1
                self._record_shadow_interpretation(message, context, snippets, tools)
            return deterministic_result, metrics

        if not self.settings.openai_api_key:
            self._record_event(message.conversation_id, "llm_api_key_missing", {})
            return deterministic_result, metrics

        provider_started = perf_counter()
        try:
            metrics["nlu_provider_used"] = "openai"
            metrics["used_openai"] = True
            metrics["openai_calls"] = 1
            result = self.nlu.interpret(message, context, snippets, tools)
            metrics["nlu_provider_ms"] = _elapsed_ms(provider_started)
            return result, metrics
        except Exception as exc:
            metrics["nlu_provider_ms"] = _elapsed_ms(provider_started)
            metrics["nlu_provider_used"] = "deterministic"
            metrics["used_fallback"] = True
            if _is_timeout_error(exc):
                metrics["timed_out_stage"] = "openai_responses"
                self._record_event(
                    message.conversation_id,
                    "nlu_provider_timeout_fallback_used",
                    {"provider": "openai"},
                )
            else:
                self._record_event(message.conversation_id, "llm_interpretation_failed", {})
            self._record_event(message.conversation_id, "nlu_failed", {})
            return deterministic_result, metrics

    def _record_shadow_interpretation(
        self,
        message: IncomingMessage,
        context: dict[str, object],
        snippets: list[KnowledgeSnippet],
        tools: list[ToolDefinition],
    ) -> None:
        try:
            shadow = self.nlu.interpret(message, context, snippets, tools)
            self._record_event(
                message.conversation_id,
                "llm_shadow_result",
                {
                    "intent": shadow.intent,
                    "confidence": shadow.confidence,
                    "signals": shadow.signals,
                },
            )
        except Exception:
            self._record_event(message.conversation_id, "llm_shadow_failed", {})

    def _normalize_inbound(self, message: IncomingMessage) -> IncomingMessage:
        return message.model_copy(update={"text": " ".join(message.text.split())})

    def _can_use_deterministic_fast_path(self, result: NLUResult) -> bool:
        del self
        return result.global_intent in {
            "cancel_flow",
            "faq",
            "handoff",
            "correction",
            "red_flag",
        }

    def _begin_trace_counters(self) -> None:
        self._trace_events_written = 0
        self._trace_event_log_ms = 0.0
        self._trace_best_effort = False

    def _record_event(
        self,
        conversation_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        started = perf_counter()
        try:
            self.events.record(conversation_id, event_type, payload)
            self._trace_events_written += 1
        except Exception:
            self._trace_best_effort = True
        finally:
            self._trace_event_log_ms += perf_counter() - started

    def _record_trace(self, conversation_id: str, trace: AuthorityTurnTrace) -> None:
        self._record_event(
            conversation_id,
            "authority_turn_timing_completed",
            trace.timing.model_dump(by_alias=True, mode="json"),
        )
        self._record_event(
            conversation_id,
            "authority_turn_completed",
            trace.model_dump(by_alias=True, mode="json"),
        )

    def _build_trace(
        self,
        *,
        turn_id: str,
        message: IncomingMessage,
        turn_started: float,
        timings: dict[str, float],
        counts: dict[str, int],
        nlu_metrics: dict[str, Any],
        state_before: ConversationState,
        state_after: ConversationState,
        nlu_result: NLUResult | None,
        applied_slots: list[str],
        ignored_slot_reasons: dict[str, str],
        action_type: str | None,
        policy_reason: str | None,
        policy_tool_name: str | None,
        render_key: str | None,
        outbox_kind: str,
        loop_prevented: bool,
    ) -> AuthorityTurnTrace:
        timing = AuthorityTurnTiming(
            totalDurationMs=_elapsed_ms(turn_started),
            loadStateMs=_seconds_to_ms(timings.get("load_state_ms", 0)),
            nluTotalMs=_seconds_to_ms(timings.get("nlu_total_ms", 0)),
            nluProviderMs=int(nlu_metrics.get("nlu_provider_ms", 0)),
            deterministicParserMs=int(nlu_metrics.get("deterministic_parser_ms", 0)),
            reducerMs=_seconds_to_ms(timings.get("reducer_ms", 0)),
            policyMs=_seconds_to_ms(timings.get("policy_ms", 0)),
            toolsMs=_seconds_to_ms(timings.get("tools_ms", 0)),
            rendererMs=_seconds_to_ms(timings.get("renderer_ms", 0)),
            persistenceMs=_seconds_to_ms(timings.get("persistence_ms", 0)),
            eventLogMs=_seconds_to_ms(self._trace_event_log_ms),
            outboxMs=_seconds_to_ms(timings.get("outbox_ms", 0)),
            openaiCalls=counts.get("openai_calls", 0),
            storeReads=counts.get("store_reads", 0),
            storeWrites=counts.get("store_writes", 0),
            eventsWritten=self._trace_events_written + 2,
            usedOpenAI=bool(nlu_metrics.get("used_openai")),
            usedFallback=bool(nlu_metrics.get("used_fallback")),
            traceBestEffort=self._trace_best_effort,
            timedOutStage=nlu_metrics.get("timed_out_stage"),
        )
        state_changed = state_before.model_dump(mode="json") != state_after.model_dump(
            mode="json"
        )
        return AuthorityTurnTrace(
            turnId=turn_id,
            conversationIdHash=_hash_id(message.conversation_id),
            channel=message.channel,
            timing=timing,
            inboundKind={
                "hasText": bool(message.text),
                "hasMedia": bool(message.media),
                "textLengthBucket": _length_bucket(message.text),
            },
            activeFlowBefore=state_before.active_flow or state_before.current_flow,
            lastBotQuestionKindBefore=state_before.last_question_kind,
            pendingFieldsBefore=list(state_before.pending_fields),
            nluCalled=nlu_result is not None,
            nluProviderUsed=nlu_metrics.get("nlu_provider_used", "skipped"),
            nluIntent=nlu_result.intent if nlu_result else None,
            nluGlobalIntent=nlu_result.global_intent if nlu_result else None,
            nluSlotsExtracted=list(nlu_result.slots) if nlu_result else [],
            nluTargetSlots=list(nlu_result.target_slots) if nlu_result else [],
            slotsApplied=applied_slots,
            slotsIgnored=[
                IgnoredSlotTrace(slotName=name, reason=reason)
                for name, reason in sorted(ignored_slot_reasons.items())
            ],
            statePatchSummary=StatePatchSummary(
                statusBefore=state_before.client_status,
                statusAfter=state_after.client_status,
                stateChanged=state_changed,
            ),
            pendingFieldsAfter=list(state_after.pending_fields),
            activeFlowAfter=state_after.active_flow or state_after.current_flow,
            policyAction=action_type,
            policyReason=policy_reason,
            hybridRoutingDecision=map_policy_to_hybrid_decision(
                action_type=action_type,
                reply_intent=policy_reason,
                reply_key=render_key,
                nlu_intent=nlu_result.intent if nlu_result else None,
                nlu_global_intent=nlu_result.global_intent if nlu_result else None,
                tool_name=policy_tool_name,
            ),
            renderKey=render_key,
            outboxKind=outbox_kind,
            legacyBypassUsed=False,
            loopPrevented=loop_prevented,
        )


@contextmanager
def _measure(timings: dict[str, float], key: str) -> Iterator[None]:
    started = perf_counter()
    try:
        yield
    finally:
        timings[key] = timings.get(key, 0.0) + (perf_counter() - started)


def _elapsed_ms(started: float) -> int:
    return _seconds_to_ms(perf_counter() - started)


def _seconds_to_ms(seconds: float) -> int:
    return int(round(seconds * 1000))


def _hash_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _length_bucket(text: str) -> str:
    length = len(text)
    if length == 0:
        return "empty"
    if length <= 20:
        return "short"
    if length <= 120:
        return "medium"
    return "long"


def _is_timeout_error(exc: Exception) -> bool:
    value = f"{type(exc).__name__} {exc}".lower()
    return "timeout" in value or "timed out" in value


def _is_return_to_bot_command(text: str) -> bool:
    normalized = " ".join(text.lower().split())
    return normalized in {
        "volver al bot",
        "reanudar bot",
        "activar bot",
        "bot",
    }
