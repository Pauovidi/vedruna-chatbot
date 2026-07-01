from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from core.conversation.actions import ConversationAction
from core.conversation.copy_renderer import RenderedReply
from core.conversation.state_manager import ConversationState
from core.llm.schemas import Channel, ToolCallRequest, ToolResult
from core.nlu.schemas import NLUResult
from core.outbox.base import OutboxMessage as CoreOutboxMessage
from core.outbox.base import OutboxResult as CoreOutboxResult


class NormalizedInbound(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    channel: Channel = "webchat"
    tenant_id: str = Field(default="default", alias="tenantId")
    client_id: str = Field(default="default", alias="clientId")
    user_id: str | None = Field(default=None, alias="userId")
    conversation_id: str = Field(alias="conversationId")
    text: str = ""
    media: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    mode: Literal["bot", "human"] = "bot"


class StateReduction(BaseModel):
    state: ConversationState
    events: list[dict[str, Any]] = Field(default_factory=list)
    applied_slots: list[str] = Field(default_factory=list)
    ignored_slots: list[str] = Field(default_factory=list)
    ignored_slot_reasons: dict[str, str] = Field(default_factory=dict)
    pending_fields: list[str] = Field(default_factory=list)


class StatePatch(BaseModel):
    updates: dict[str, Any] = Field(default_factory=dict)
    applied_slots: list[str] = Field(default_factory=list)
    ignored_slots: dict[str, str] = Field(default_factory=dict)
    pending_fields: list[str] = Field(default_factory=list)


class IgnoredSlotTrace(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    slot_name: str = Field(alias="slotName")
    reason: str


class StatePatchSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status_before: str | None = Field(default=None, alias="statusBefore")
    status_after: str | None = Field(default=None, alias="statusAfter")
    state_changed: bool = Field(default=False, alias="stateChanged")


class AuthorityTurnTiming(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total_duration_ms: int = Field(default=0, alias="totalDurationMs")
    load_state_ms: int = Field(default=0, alias="loadStateMs")
    nlu_total_ms: int = Field(default=0, alias="nluTotalMs")
    nlu_provider_ms: int = Field(default=0, alias="nluProviderMs")
    deterministic_parser_ms: int = Field(default=0, alias="deterministicParserMs")
    reducer_ms: int = Field(default=0, alias="reducerMs")
    policy_ms: int = Field(default=0, alias="policyMs")
    tools_ms: int = Field(default=0, alias="toolsMs")
    renderer_ms: int = Field(default=0, alias="rendererMs")
    persistence_ms: int = Field(default=0, alias="persistenceMs")
    event_log_ms: int = Field(default=0, alias="eventLogMs")
    outbox_ms: int = Field(default=0, alias="outboxMs")
    openai_calls: int = Field(default=0, alias="openaiCalls")
    store_reads: int = Field(default=0, alias="storeReads")
    store_writes: int = Field(default=0, alias="storeWrites")
    events_written: int = Field(default=0, alias="eventsWritten")
    used_openai: bool = Field(default=False, alias="usedOpenAI")
    used_fallback: bool = Field(default=False, alias="usedFallback")
    trace_best_effort: bool = Field(default=False, alias="traceBestEffort")
    timed_out_stage: str | None = Field(default=None, alias="timedOutStage")


class AuthorityTurnTrace(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    turn_id: str = Field(alias="turnId")
    conversation_id_hash: str = Field(alias="conversationIdHash")
    channel: Channel
    timing: AuthorityTurnTiming
    inbound_kind: dict[str, Any] = Field(default_factory=dict, alias="inboundKind")
    active_flow_before: str | None = Field(default=None, alias="activeFlowBefore")
    last_bot_question_kind_before: str | None = Field(
        default=None, alias="lastBotQuestionKindBefore"
    )
    pending_fields_before: list[str] = Field(default_factory=list, alias="pendingFieldsBefore")
    nlu_called: bool = Field(default=False, alias="nluCalled")
    nlu_provider_used: Literal["openai", "deterministic", "skipped"] = Field(
        default="skipped", alias="nluProviderUsed"
    )
    nlu_intent: str | None = Field(default=None, alias="nluIntent")
    nlu_global_intent: str | None = Field(default=None, alias="nluGlobalIntent")
    nlu_slots_extracted: list[str] = Field(default_factory=list, alias="nluSlotsExtracted")
    nlu_target_slots: list[str] = Field(default_factory=list, alias="nluTargetSlots")
    slots_applied: list[str] = Field(default_factory=list, alias="slotsApplied")
    slots_ignored: list[IgnoredSlotTrace] = Field(default_factory=list, alias="slotsIgnored")
    state_patch_summary: StatePatchSummary = Field(
        default_factory=StatePatchSummary, alias="statePatchSummary"
    )
    pending_fields_after: list[str] = Field(default_factory=list, alias="pendingFieldsAfter")
    active_flow_after: str | None = Field(default=None, alias="activeFlowAfter")
    policy_action: str | None = Field(default=None, alias="policyAction")
    policy_reason: str | None = Field(default=None, alias="policyReason")
    render_key: str | None = Field(default=None, alias="renderKey")
    outbox_kind: Literal["outbox_send", "dry_run", "suppressed"] = Field(
        default="suppressed", alias="outboxKind"
    )
    legacy_bypass_used: bool = Field(default=False, alias="legacyBypassUsed")
    legacy_bypass_name: str | None = Field(default=None, alias="legacyBypassName")
    loop_prevented: bool = Field(default=False, alias="loopPrevented")


class PolicyEngine(Protocol):
    def decide(
        self,
        state: ConversationState,
        nlu_result: NLUResult,
        tool_results: list[ToolResult] | None = None,
    ) -> ConversationAction:
        ...


class StateReducer(Protocol):
    def reduce(
        self,
        state: ConversationState,
        inbound: NormalizedInbound,
        nlu_result: NLUResult,
    ) -> StateReduction:
        ...


class ToolExecutionRuntime(Protocol):
    def execute(self, tool_call: ToolCallRequest) -> ToolResult:
        ...


class CopyRenderingRuntime(Protocol):
    def render(
        self,
        action: ConversationAction,
        state: ConversationState,
        tool_result: ToolResult | None = None,
    ) -> RenderedReply:
        ...


StateReducerResult = StateReduction
ToolCall = ToolCallRequest
RenderedMessage = RenderedReply
OutboxMessage = CoreOutboxMessage
OutboxResult = CoreOutboxResult
