from __future__ import annotations

from core.knowledge.retriever import SimpleKnowledgeRetriever
from core.knowledge.schemas import KnowledgeEntry


def test_retrieval_returns_small_snippets_not_whole_knowledge() -> None:
    long_content = "precio " + ("detalle interno " * 100)
    retriever = SimpleKnowledgeRetriever(
        [
            KnowledgeEntry(
                id="a",
                client_id="demo",
                title="Precios",
                content=long_content,
                tags=["precio"],
            ),
            KnowledgeEntry(
                id="b",
                client_id="demo",
                title="Otro",
                content="mudanza ascensor",
            ),
        ]
    )
    snippets = retriever.search_knowledge("precio mudanza", "demo", top_k=1)
    assert len(snippets) == 1
    assert snippets[0].source_id == "a"
    assert len(snippets[0].snippet) < len(long_content)
    assert "detalle interno " * 20 not in snippets[0].snippet
