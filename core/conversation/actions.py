from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ActionType = Literal[
    "answer_information",
    "ask_missing_context",
    "clarify_scope",
    "cancel_flow",
    "handoff_visible",
    "call_tool",
    "confirm_before_action",
    "fallback_contextual",
    "red_flag_handoff",
    "reset_conversation",
    "continue_existing_flow",
    "no_reply_human_mode",
]


class ConversationAction(BaseModel):
    action_type: ActionType
    reply_intent: str
    reply_key: str
    visible_reply_required: bool = True
    visible_handoff_required: bool = False
    target: str | None = None
    target_department: str | None = None
    target_role: str | None = None
    requires_tool: bool = False
    tool_name: str | None = None
    tool_arguments: dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = False
    handoff_reason: str | None = None
    state_updates: dict[str, Any] = Field(default_factory=dict)
    safety_level: Literal["low", "medium", "high", "critical"] = "low"
    metadata: dict[str, Any] = Field(default_factory=dict)
    allowed_copy_style: str = "brief_human"
    requires_human: bool = False
