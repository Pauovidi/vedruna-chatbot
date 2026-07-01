from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class N8NWorkflowRequest:
    workflow_name: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class N8NWorkflowResult:
    status: str
    user_safe_summary: str
    data: dict[str, Any]


class N8NWorkflowAdapter:
    """Stub boundary for n8n workflows.

    This adapter deliberately does not decide conversation actions, render user copy,
    keep conversation state, or bypass tool policy. A future real implementation can
    be registered as a tool handler after ConversationPolicy authorizes the action.
    """

    def execute(self, request: N8NWorkflowRequest) -> N8NWorkflowResult:
        return N8NWorkflowResult(
            status="dry_run",
            user_safe_summary="Workflow preparado como propuesta; no se ha ejecutado.",
            data={"workflow_name": request.workflow_name, "payload_redacted": True},
        )
