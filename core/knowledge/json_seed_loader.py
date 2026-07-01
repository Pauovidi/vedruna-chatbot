from __future__ import annotations

import json
from pathlib import Path

from core.knowledge.schemas import KnowledgeEntry


def load_seed(path: Path, client_id: str) -> list[KnowledgeEntry]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("entries", payload if isinstance(payload, list) else [])
    return [
        KnowledgeEntry.model_validate({**entry, "client_id": client_id})
        for entry in entries
    ]
