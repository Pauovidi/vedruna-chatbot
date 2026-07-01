from __future__ import annotations

from dataclasses import dataclass

from core.llm.schemas import Channel, ToolCallRequest
from core.tools.schemas import ToolDefinition


@dataclass(frozen=True)
class ToolPolicyContext:
    channel: Channel
    confirmed: bool = False
    flags: dict[str, bool] | None = None


@dataclass(frozen=True)
class ToolPolicyDecision:
    allowed: bool
    reason: str


def validate_tool_call(
    request: ToolCallRequest,
    definition: ToolDefinition | None,
    context: ToolPolicyContext,
) -> ToolPolicyDecision:
    if definition is None:
        return ToolPolicyDecision(False, "unknown_tool")
    if context.channel not in definition.allowed_channels:
        return ToolPolicyDecision(False, "channel_not_allowed")
    if definition.required_confirmation or request.requires_confirmation:
        if not context.confirmed:
            return ToolPolicyDecision(False, "confirmation_required")
    flags = context.flags or {}
    missing_flags = [
        flag for flag in definition.required_flags if not flags.get(flag, False)
    ]
    if missing_flags:
        return ToolPolicyDecision(False, "required_flag_disabled")
    return ToolPolicyDecision(True, "allowed")
