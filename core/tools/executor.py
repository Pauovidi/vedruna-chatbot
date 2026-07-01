from __future__ import annotations

from typing import Any

from core.llm.schemas import IncomingMessage, ToolCallRequest, ToolResult
from core.observability.events import EventRecorder
from core.tools.policy import ToolPolicyContext, validate_tool_call
from core.tools.registry import ToolRegistry
from core.tools.schemas import ToolHandler


class ToolExecutor:
    def __init__(
        self,
        registry: ToolRegistry,
        recorder: EventRecorder | None = None,
        handlers: dict[str, ToolHandler] | None = None,
    ):
        self.registry = registry
        self.recorder = recorder or EventRecorder()
        self.handlers = handlers or {}

    def execute(
        self,
        request: ToolCallRequest,
        message: IncomingMessage,
        *,
        confirmed: bool = False,
        flags: dict[str, bool] | None = None,
    ) -> ToolResult:
        definition = self.registry.get(request.name)
        self.recorder.record(message.conversation_id, "tool_requested", {"name": request.name})
        self.recorder.record(message.conversation_id, "tool_called", {"name": request.name})
        effective_request = request
        if definition is not None:
            effective_request = request.model_copy(
                update={
                    "risk_level": definition.risk_level,
                    "requires_confirmation": (
                        definition.required_confirmation or request.requires_confirmation
                    ),
                }
            )
        decision = validate_tool_call(
            effective_request,
            definition,
            ToolPolicyContext(
                channel=message.channel,
                confirmed=confirmed,
                flags=flags,
            ),
        )
        if not decision.allowed:
            self.recorder.record(
                message.conversation_id,
                "tool_blocked",
                {"name": request.name, "reason": decision.reason},
            )
            result = ToolResult(
                name=request.name,
                status="blocked",
                user_safe_summary="Necesito confirmarlo o revisarlo antes de hacerlo.",
                internal_code=decision.reason,
            )
            self.recorder.record_tool_call(
                message.conversation_id,
                result.name,
                result.status,
                result.model_dump(mode="json"),
            )
            return result
        self.recorder.record(message.conversation_id, "tool_allowed", {"name": request.name})
        try:
            result = self._execute_handler(effective_request, message)
        except Exception:
            result = ToolResult(
                name=request.name,
                status="failed",
                user_safe_summary="No he podido completar la accion ahora.",
                internal_code="handler_exception",
            )
            self.recorder.record(
                message.conversation_id,
                "tool_failed",
                {"name": request.name, "reason": "handler_exception"},
            )
        self.recorder.record_tool_call(
            message.conversation_id,
            result.name,
            result.status,
            result.model_dump(mode="json"),
        )
        self.recorder.record(
            message.conversation_id,
            "tool_completed",
            {"name": request.name, "status": result.status},
        )
        self.recorder.record(
            message.conversation_id,
            "tool_result",
            {"name": request.name, "status": result.status},
        )
        return result

    def _execute_handler(
        self,
        request: ToolCallRequest,
        message: IncomingMessage,
    ) -> ToolResult:
        definition = self.registry.get(request.name)
        handler_key = definition.handler if definition is not None else request.name
        handler = self.handlers.get(handler_key) or self.handlers.get(request.name)
        if handler is None:
            return self._stub_handler(request)
        return handler.execute(
            request,
            {
                "conversation_id": message.conversation_id,
                "client_id": message.client_id,
                "channel": message.channel,
            },
        )

    def _stub_handler(self, request: ToolCallRequest) -> ToolResult:
        data: dict[str, Any] = {"arguments_redacted": True}
        if request.name == "handoff_to_human":
            return ToolResult(
                name=request.name,
                status="success",
                user_safe_summary="He dejado aviso para que una persona lo revise.",
                data=data,
            )
        return ToolResult(
            name=request.name,
            status="dry_run",
            user_safe_summary="Solicitud registrada en modo de prueba.",
            internal_code="stub_handler",
            data=data,
        )
