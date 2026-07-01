from __future__ import annotations

from core.testing.golden_runner import run_all_golden_suites


def test_golden_runner_executes_client_suites() -> None:
    summary = run_all_golden_suites()
    assert summary["passed"] >= 8
