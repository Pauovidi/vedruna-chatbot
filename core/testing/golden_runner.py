from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

from core.adapters.vedruna.tools import get_vedruna_tool_handlers
from core.clients import list_client_ids, load_client_tools
from core.config import ROOT_DIR, Settings
from core.conversation.orchestrator import ConversationOrchestrator
from core.conversation.state_manager import StateManager
from core.knowledge.json_seed_loader import load_seed
from core.knowledge.retriever import SimpleKnowledgeRetriever
from core.llm.openai_provider import OpenAIProvider
from core.llm.schemas import IncomingMessage
from core.observability.events import EventRecorder
from core.persistence.memory import MemoryStore
from core.tools.registry import ToolRegistry


def run_all_golden_suites(root_dir: Path = ROOT_DIR) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for client_id in list_client_ids(root_dir):
        path = root_dir / "clients" / client_id / "golden_tests.yaml"
        if not path.exists():
            continue
        results.extend(run_golden_suite(path, client_id, root_dir))
    return {"passed": len(results), "cases": results}


def run_golden_suite(
    path: Path,
    client_id: str,
    root_dir: Path = ROOT_DIR,
) -> list[dict[str, Any]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cases = payload.get("cases", [])
    results = []
    for index, case in enumerate(cases, start=1):
        orchestrator = _make_orchestrator(root_dir)
        conversation_id = f"golden-{client_id}-{index}"
        turns = case.get("multi_turn") or [case]
        last_result = None
        for turn_index, turn in enumerate(turns, start=1):
            last_result = orchestrator.handle_turn(
                IncomingMessage(
                    conversation_id=conversation_id,
                    client_id=client_id,
                    channel=turn.get("channel", case.get("channel", "whatsapp")),
                    text=turn["input"],
                )
            )
            _assert_turn(turn, last_result)
            results.append(
                {
                    "client_id": client_id,
                    "case": case["name"],
                    "turn": turn_index,
                    "reply_key": last_result.reply_key,
                    "action_type": last_result.action_type,
                }
            )
        if last_result is None:
            raise AssertionError(f"Golden case has no turns: {case['name']}")
    return results


def _assert_turn(expectation: dict[str, Any], result) -> None:
    if expected := expectation.get("expected_intent"):
        assert result.intent == expected, (result.intent, expected)
    if expected := expectation.get("expected_action_type"):
        assert result.action_type == expected, (result.action_type, expected)
    if expected := expectation.get("expected_reply_key"):
        assert result.reply_key == expected, (result.reply_key, expected)
    if expected := expectation.get("expected_requires_human"):
        assert result.requires_human is bool(expected), result
    for expected in expectation.get("expected_contains", []):
        assert expected.lower() in result.reply_text.lower(), result.reply_text
    for forbidden in expectation.get("forbidden_contains", []):
        assert forbidden.lower() not in result.reply_text.lower(), result.reply_text
    if expected_sources := expectation.get("expected_source_ids"):
        for expected_source in expected_sources:
            assert expected_source in result.source_ids, (result.source_ids, expected_sources)


def _make_orchestrator(root_dir: Path) -> ConversationOrchestrator:
    settings = Settings(
        OPENAI_API_KEY="",
        CONVERSATIONAL_REPLY_ENABLED=False,
        CONVERSATIONAL_REPLY_SHADOW=False,
        DATABASE_URL="",
    )
    store = MemoryStore()
    retriever = SimpleKnowledgeRetriever()
    for seed in (root_dir / "clients").glob("*/knowledge_seed.json"):
        retriever.add_entries(load_seed(seed, seed.parent.name))
    registry = ToolRegistry()
    registry.extend(load_client_tools(root_dir))
    return ConversationOrchestrator(
        OpenAIProvider(settings),
        StateManager(store),
        retriever,
        registry,
        EventRecorder(store),
        settings=settings,
        tool_handlers=get_vedruna_tool_handlers(settings),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root-dir", type=Path, default=ROOT_DIR)
    args = parser.parse_args()
    summary = run_all_golden_suites(args.root_dir)
    print(f"golden suites passed: {summary['passed']}")


if __name__ == "__main__":
    main()
