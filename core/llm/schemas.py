from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Channel = Literal["whatsapp", "webchat", "voice"]
ToolStatus = Literal["success", "blocked", "failed", "dry_run"]
RiskLevel = Literal["low", "medium", "high", "critical"]


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
    risk_level: RiskLevel = "low"
    requires_confirmation: bool = False


class ToolResult(BaseModel):
    name: str
    status: ToolStatus
    user_safe_summary: str
    internal_code: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class IncomingMessage(BaseModel):
    channel: Channel = "webchat"
    conversation_id: str
    client_id: str = "default"
    user_id: str | None = None
    phone_redacted: str | None = None
    text: str
    media: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatTurnResult(BaseModel):
    conversation_id: str
    reply_text: str
    requires_human: bool = False
    priority: bool = False
    source_ids: list[str] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    mode: Literal["bot", "human"] = "bot"
    intent: str | None = None
    action_type: str | None = None
    reply_key: str | None = None
    authority_trace: dict[str, Any] | None = None
