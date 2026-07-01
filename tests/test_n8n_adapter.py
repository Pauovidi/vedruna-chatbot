from __future__ import annotations

from core.adapters.n8n import N8NWorkflowAdapter, N8NWorkflowRequest
from core.conversation.actions import ConversationAction
from core.conversation.state_manager import ConversationState
from core.llm.schemas import IncomingMessage, ToolCallRequest, ToolResult
from core.observability.events import EventRecorder
from core.persistence.memory import MemoryStore
from core.tools.executor import ToolExecutor
from core.tools.registry import ToolRegistry
from core.tools.schemas import ToolDefinition, ToolHandler


class N8NToolHandler(ToolHandler):
    def __init__(self) -> None:
        self.calls = 0
        self.adapter = N8NWorkflowAdapter()

    def execute(
        self,
        request: ToolCallRequest,
        context: dict[str, object],
    ) -> ToolResult:
        self.calls += 1
        result = self.adapter.execute(
            N8NWorkflowRequest(
                workflow_name=str(request.arguments.get("workflow_name", "demo")),
                payload={"context": context},
            )
        )
        return ToolResult(
            name=request.name,
            status=result.status,
            user_safe_summary=result.user_safe_summary,
            data=result.data,
        )


def test_n8n_adapter_does_not_create_action_copy_or_state() -> None:
    result = N8NWorkflowAdapter().execute(
        N8NWorkflowRequest(workflow_name="lead", payload={"field": "value"})
    )
    assert not isinstance(result, ConversationAction)
    assert not isinstance(result, ConversationState)
    assert hasattr(result, "user_safe_summary")
    assert not hasattr(result, "reply_key")
    assert not hasattr(result, "text")


def test_n8n_handler_only_runs_after_tool_policy_allows_it() -> None:
    registry = ToolRegistry([])
    registry.extend(
        [
            ToolDefinition(
                name="run_n8n_workflow",
                description="Run an authorized external workflow.",
                risk_level="medium",
                required_confirmation=True,
                required_flags=["workflow_enabled"],
                handler="n8n",
            )
        ]
    )
    store = MemoryStore()
    handler = N8NToolHandler()
    executor = ToolExecutor(
        registry,
        EventRecorder(store),
        handlers={"n8n": handler},
    )
    message = IncomingMessage(conversation_id="n8n-1", text="run")
    request = ToolCallRequest(
        name="run_n8n_workflow",
        arguments={"workflow_name": "lead"},
        requires_confirmation=True,
    )

    blocked = executor.execute(
        request,
        message,
        confirmed=False,
        flags={"workflow_enabled": True},
    )
    allowed = executor.execute(
        request,
        message,
        confirmed=True,
        flags={"workflow_enabled": True},
    )

    assert blocked.status == "blocked"
    assert handler.calls == 1
    assert allowed.status == "dry_run"
