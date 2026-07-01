from __future__ import annotations

from core.knowledge.schemas import KnowledgeEntry


class PostgresKnowledgeStore:
    """Placeholder for V1 durable knowledge import/search."""

    def __init__(self, database_url: str):
        self.database_url = database_url

    def import_entries(self, entries: list[KnowledgeEntry]) -> int:
        return len(entries)
