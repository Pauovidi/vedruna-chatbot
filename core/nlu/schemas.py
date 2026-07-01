from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from core.knowledge.schemas import KnowledgeSnippet
from core.llm.schemas import IncomingMessage
from core.tools.schemas import ToolDefinition


class NLUResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: str = "unknown"
    global_intent: str | None = None
    domain_intent: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    entities: dict[str, Any] = Field(default_factory=dict)
    slots: dict[str, Any] = Field(default_factory=dict)
    target_slots: dict[str, Any] = Field(default_factory=dict)
    signals: list[str] = Field(default_factory=list)
    raw_user_reply_type: str = "free_text"
    contextual_reply_to_last_question: bool = False
    active_topic_hint: str | None = None
    is_information_only: bool = False
    is_negative_appointment: bool = False
    is_price_question: bool = False
    safety_signals: list[str] = Field(default_factory=list)
    safety: dict[str, Any] = Field(default_factory=dict)
    ambiguity: dict[str, Any] = Field(default_factory=dict)
    raw_provider_info_sanitized: dict[str, Any] = Field(default_factory=dict)
    language: str = "es"
    tone_hints: list[str] = Field(default_factory=list)


class NLUInterpreter(Protocol):
    def interpret(
        self,
        message: IncomingMessage,
        context: dict[str, object],
        snippets: list[KnowledgeSnippet],
        tools: list[ToolDefinition],
    ) -> NLUResult:
        ...
