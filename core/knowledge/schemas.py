from __future__ import annotations

from pydantic import BaseModel, Field


class KnowledgeEntry(BaseModel):
    id: str
    client_id: str
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class KnowledgeSnippet(BaseModel):
    id: str
    title: str
    snippet: str
    score: float
    source_id: str
