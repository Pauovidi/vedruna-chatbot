from __future__ import annotations

import re
from collections.abc import Iterable

from core.knowledge.schemas import KnowledgeEntry, KnowledgeSnippet

TOKEN_RE = re.compile(r"[a-zA-ZáéíóúÁÉÍÓÚñÑ0-9]+")


def tokenize(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(text)}


class SimpleKnowledgeRetriever:
    def __init__(self, entries: Iterable[KnowledgeEntry] | None = None):
        self.entries = list(entries or [])

    def add_entries(self, entries: Iterable[KnowledgeEntry]) -> None:
        self.entries.extend(entries)

    def search_knowledge(
        self,
        query: str,
        client_id: str,
        top_k: int = 3,
    ) -> list[KnowledgeSnippet]:
        query_tokens = tokenize(query)
        scored: list[tuple[float, KnowledgeEntry]] = []
        for entry in self.entries:
            if entry.client_id != client_id:
                continue
            haystack = tokenize(" ".join([entry.title, entry.content, *entry.tags]))
            exact = len(query_tokens & haystack)
            related = sum(
                1
                for query_token in query_tokens
                if any(_related(query_token, token) for token in haystack)
            )
            score = max(exact, related * 0.6) / max(len(query_tokens), 1)
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            KnowledgeSnippet(
                id=entry.id,
                title=entry.title,
                snippet=_compact(entry.content),
                score=score,
                source_id=entry.id,
            )
            for score, entry in scored[:top_k]
        ]


def _related(left: str, right: str) -> bool:
    if len(left) < 5 or len(right) < 5:
        return False
    return left.startswith(right[:5]) or right.startswith(left[:5])


def _compact(content: str, max_chars: int = 220) -> str:
    normalized = " ".join(content.split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 3].rstrip() + "..."
