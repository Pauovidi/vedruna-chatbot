from __future__ import annotations

from core.clients import load_client_tools
from core.llm.schemas import ToolCallRequest
from core.tools.policy import ToolPolicyContext, validate_tool_call
from core.tools.registry import ToolRegistry


def test_tool_policy_blocks_critical_without_confirmation() -> None:
    registry = ToolRegistry()
    request = ToolCallRequest(name="confirm_cancellation", requires_confirmation=True)
    decision = validate_tool_call(
        request,
        registry.get("confirm_cancellation"),
        ToolPolicyContext(
            channel="whatsapp",
            confirmed=False,
            flags={"appointments_enabled": True},
        ),
    )
    assert decision.allowed is False
    assert decision.reason == "confirmation_required"


def test_tool_policy_blocks_required_flag_false() -> None:
    registry = ToolRegistry()
    request = ToolCallRequest(name="confirm_reschedule", requires_confirmation=True)
    decision = validate_tool_call(
        request,
        registry.get("confirm_reschedule"),
        ToolPolicyContext(
            channel="webchat",
            confirmed=True,
            flags={"appointments_enabled": False},
        ),
    )
    assert decision.allowed is False
    assert decision.reason == "required_flag_disabled"


def test_client_tools_are_declarative_and_loadable() -> None:
    tool_names = {tool.name for tool in load_client_tools()}
    assert "create_quote_lead" in tool_names
    assert "search_availability_stub" in tool_names
