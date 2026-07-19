from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from core.adapters.vedruna.tools import get_vedruna_tool_handlers
from core.clients import load_client_tools
from core.config import ROOT_DIR, Settings
from core.conversation.orchestrator import ConversationOrchestrator
from core.conversation.state_manager import StateManager
from core.knowledge.retriever import SimpleKnowledgeRetriever
from core.llm.openai_provider import OpenAIProvider
from core.llm.schemas import IncomingMessage
from core.observability.events import Event
from core.persistence.memory import MemoryStore
from core.tools.registry import ToolRegistry


def run_latency_smoke(root_dir: Path = ROOT_DIR) -> list[dict[str, Any]]:
    settings = Settings(
        OPENAI_API_KEY="",
        CONVERSATIONAL_REPLY_ENABLED=False,
        CONVERSATIONAL_REPLY_SHADOW=False,
        DATABASE_URL="",
    )
    store = MemoryStore()
    registry = ToolRegistry()
    registry.extend(load_client_tools(root_dir))
    orchestrator = ConversationOrchestrator(
        OpenAIProvider(settings),
        StateManager(store),
        SimpleKnowledgeRetriever(),
        registry,
        EventRecorderAdapter(store),
        settings=settings,
        tool_handlers=get_vedruna_tool_handlers(settings),
    )
    turns = [
        "hola",
        "quiero reservar",
        "mañana",
        "a las 10",
        "a la misma hora",
        "cuanto cuesta?",
        "no quiero seguir",
    ]
    rows: list[dict[str, Any]] = []
    for index, text in enumerate(turns):
        conversation_id = "latency-smoke-1"
        orchestrator.handle_turn(
            IncomingMessage(
                conversation_id=conversation_id,
                client_id="generic_core_example",
                channel="whatsapp",
                text=text,
            )
        )
        timing = _latest_event_payload(
            store.list_events(conversation_id),
            "authority_turn_timing_completed",
        )
        assert timing is not None, "missing authority_turn_timing_completed"
        assert timing["totalDurationMs"] >= 0
        rows.append({"turn": index + 1, "textKind": _text_kind(text), **timing})
    return rows


def _latest_event_payload(events: list[Event], event_type: str) -> dict[str, Any] | None:
    matches = [event.payload for event in events if event.type == event_type]
    return matches[-1] if matches else None


def _text_kind(text: str) -> str:
    if "?" in text:
        return "faq"
    if "no quiero" in text:
        return "cancel"
    if "misma hora" in text:
        return "same_time"
    if any(char.isdigit() for char in text):
        return "time"
    return "general"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root-dir", type=Path, default=ROOT_DIR)
    args = parser.parse_args()
    rows = run_latency_smoke(args.root_dir)
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    print(f"latency smoke passed: {len(rows)}")


class EventRecorderAdapter:
    def __init__(self, store: MemoryStore) -> None:
        from core.observability.events import EventRecorder

        self._recorder = EventRecorder(store)

    def record(self, conversation_id: str, event_type: str, payload: dict[str, Any]) -> None:
        self._recorder.record(conversation_id, event_type, payload)

    def record_many(self, events: list[tuple[str, str, dict[str, Any]]]) -> None:
        self._recorder.record_many(events)

    def record_tool_call(
        self,
        conversation_id: str,
        name: str,
        status: str,
        payload: dict[str, Any],
    ) -> None:
        self._recorder.record_tool_call(conversation_id, name, status, payload)

    def list_for(self, conversation_id: str) -> list[Event]:
        return self._recorder.list_for(conversation_id)


if __name__ == "__main__":
    main()
