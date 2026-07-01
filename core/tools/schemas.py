from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field

from core.llm.schemas import Channel, RiskLevel, ToolCallRequest, ToolResult


class ToolDefinition(BaseModel):
    name: str
    description: str
    risk_level: RiskLevel = "low"
    required_confirmation: bool = False
    required_flags: list[str] = Field(default_factory=list)
    allowed_channels: list[Channel] = Field(
        default_factory=lambda: ["whatsapp", "webchat", "voice"]
    )
    handler: str = "stub"


class ToolHandler(Protocol):
    def execute(self, request: ToolCallRequest, context: dict[str, Any]) -> ToolResult:
        ...
