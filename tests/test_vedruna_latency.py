from __future__ import annotations

from tests.vedruna_helpers import make_vedruna_orchestrator, turn


def test_vedruna_latency_trace_contains_required_stages() -> None:
    orchestrator, store = make_vedruna_orchestrator()
    result = turn(orchestrator, "precio en Santa Isabel", conversation_id="latency-v")
    timing_events = [
        event.payload
        for event in store.list_events("latency-v")
        if event.type == "authority_turn_timing_completed"
    ]
    assert timing_events
    timing = timing_events[-1]
    assert timing["totalDurationMs"] >= 0
    assert timing["nluTotalMs"] >= 0
    assert timing["policyMs"] >= 0
    assert timing["rendererMs"] >= 0
    assert result.reply_text
