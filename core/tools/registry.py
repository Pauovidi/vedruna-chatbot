from __future__ import annotations

from collections.abc import Iterable

from core.tools.builtin_tools import BUILTIN_TOOLS
from core.tools.schemas import ToolDefinition


class ToolRegistry:
    def __init__(self, tools: Iterable[ToolDefinition] | None = None):
        self._tools = {tool.name: tool for tool in (tools or BUILTIN_TOOLS)}

    def names(self) -> list[str]:
        return sorted(self._tools)

    def list(self) -> list[ToolDefinition]:
        return [self._tools[name] for name in self.names()]

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def extend(self, tools: Iterable[ToolDefinition]) -> None:
        for tool in tools:
            self._tools[tool.name] = tool
