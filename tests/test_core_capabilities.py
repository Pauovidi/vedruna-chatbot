from __future__ import annotations

from datetime import datetime, timedelta

from core.identity import ClientDirectoryEntry, MemoryClientDirectory
from core.llm.schemas import IncomingMessage
from core.nlu.deterministic_interpreter import DeterministicNLUInterpreter
from core.policy.global_intents import resolve_global_intent
from core.policy.terms import TermsGateInput, evaluate_terms_gate
from core.scheduler import MemoryScheduledTaskStore, ScheduledTask, ScheduledTaskDispatcher
from core.slots import SlotMergeInput, merge_slots
from core.templates import TemplatePreviewRequest, preview_template
from core.testing.fuzz_runner import run_fuzz_cases
from core.testing.latency_smoke import run_latency_smoke


def test_slot_merge_applies_pending_and_out_of_order_corrections() -> None:
    result = merge_slots(
        SlotMergeInput(
            current_slots={"date": "2026-07-01", "count": 1},
            incoming_slots={"count": 8, "time": "10:00"},
            pending_fields=["time"],
            corrections=["count"],
            allow_out_of_order=True,
        )
    )
    assert result.slots["count"] == 8
    assert result.slots["time"] == "10:00"
    assert set(result.applied) == {"count", "time"}
    assert result.pending_fields == []


def test_slot_merge_targets_current_pending_and_reuses_same_time() -> None:
    result = merge_slots(
        SlotMergeInput(
            current_slots={"entry_time": "10:00"},
            incoming_slots={"time": "same_time"},
            target_slots={"time": "currentPending"},
            pending_fields=["exit_time"],
        )
    )
    assert result.slots["exit_time"] == "10:00"
    assert result.applied == ["exit_time"]
    assert result.pending_fields == []


def test_global_intent_escape_hatch_wins_inside_active_flow() -> None:
    nlu = DeterministicNLUInterpreter().interpret(
        IncomingMessage(conversation_id="escape-1", text="cuanto cuesta?"),
        {"current_flow": "reservation"},
        [],
        [],
    )
    decision = resolve_global_intent(nlu)
    assert decision.intent == "faq"
    assert decision.should_escape_active_flow is True


def test_terms_gate_blocks_critical_action_until_acceptance() -> None:
    blocked = evaluate_terms_gate(
        TermsGateInput(
            terms_url="https://example.invalid/terms",
            terms_version="v1",
            user_message="confirmo",
            critical_action_requested=True,
        )
    )
    accepted = evaluate_terms_gate(
        TermsGateInput(
            terms_url="https://example.invalid/terms",
            terms_version="v1",
            user_message="acepto",
            critical_action_requested=True,
        )
    )
    assert blocked.allowed is False
    assert blocked.requires_terms_link is True
    assert accepted.allowed is True
    assert accepted.terms_source == "user_message"


def test_scheduled_tasks_dedupe_and_dry_run_dispatch() -> None:
    store = MemoryScheduledTaskStore()
    now = datetime.utcnow()
    first = store.upsert(
        ScheduledTask(
            task_type="followup",
            channel="whatsapp",
            payload={"message": "hello"},
            scheduled_at=now - timedelta(minutes=1),
            dedupe_key="conv-1:followup",
            dry_run=True,
        )
    )
    second = store.upsert(
        ScheduledTask(
            task_type="followup",
            channel="whatsapp",
            payload={"message": "updated"},
            scheduled_at=now - timedelta(minutes=1),
            dedupe_key="conv-1:followup",
            dry_run=True,
        )
    )
    result = ScheduledTaskDispatcher(store).dispatch_due(now=now)
    assert second.id == first.id
    assert result.processed == 1
    assert result.dry_run == 1
    assert store.get_by_dedupe_key("conv-1:followup") is not None


def test_template_preview_never_executes_or_sends() -> None:
    result = preview_template(
        TemplatePreviewRequest(
            template_key="confirmation",
            sample_data={"client": "Sample"},
            enabled=True,
        )
    )
    assert "confirmation" in result.rendered_text
    assert result.executed_actions is False
    assert result.enqueued_messages is False
    assert result.sent_messages is False


def test_identity_directory_resolves_known_ambiguous_blocked_and_cache() -> None:
    directory = MemoryClientDirectory(
        [
            ClientDirectoryEntry(
                external_id="client-1",
                lookup_key="lookup-known",
                display_name="  Sample Client  ",
            ),
            ClientDirectoryEntry(external_id="client-2", lookup_key="lookup-ambiguous"),
            ClientDirectoryEntry(external_id="client-3", lookup_key="lookup-ambiguous"),
            ClientDirectoryEntry(
                external_id="client-4",
                lookup_key="lookup-blocked",
                blocked=True,
            ),
        ],
        ttl_seconds=60,
    )

    known = directory.resolve("lookup-known")
    cached = directory.resolve("lookup-known")
    ambiguous = directory.resolve("lookup-ambiguous")
    blocked = directory.resolve("lookup-blocked")
    unknown = directory.resolve("missing")

    assert known.status == "known"
    assert known.display_name_safe == "Sample Client"
    assert cached.cache_hit is True
    assert ambiguous.status == "ambiguous"
    assert blocked.status == "blocked"
    assert unknown.status == "unknown"


def test_generic_fuzz_runner_cases() -> None:
    results = run_fuzz_cases()
    assert len(results) >= 10


def test_latency_smoke_emits_authority_timing_rows() -> None:
    rows = run_latency_smoke()
    assert len(rows) >= 7
    assert all(row["totalDurationMs"] >= 0 for row in rows)
    assert all(row["openaiCalls"] == 0 for row in rows)
