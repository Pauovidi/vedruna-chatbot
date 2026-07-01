from __future__ import annotations


def compact_context(messages: list[dict[str, str]], limit: int = 6) -> str:
    recent = messages[-limit:]
    return " | ".join(f"{msg['role']}: {msg['text']}" for msg in recent)
