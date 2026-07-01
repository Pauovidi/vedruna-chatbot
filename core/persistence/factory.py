from __future__ import annotations

from core.config import Settings
from core.persistence.memory import MemoryStore
from core.persistence.sqlalchemy_store import SQLAlchemyConversationStore


def build_conversation_store(settings: Settings):
    settings.assert_production_ready()
    if not settings.database_url:
        return MemoryStore()
    if settings.database_url.startswith(("sqlite", "postgres")):
        return SQLAlchemyConversationStore(settings.database_url)
    raise RuntimeError("DATABASE_URL must use sqlite or postgres for this core")
