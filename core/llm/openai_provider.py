from __future__ import annotations

from typing import NoReturn

from core.config import Settings
from core.knowledge.schemas import KnowledgeSnippet
from core.llm.schemas import IncomingMessage
from core.nlu.openai_interpreter import OpenAIInterpreter
from core.nlu.schemas import NLUResult
from core.tools.schemas import ToolDefinition


class OpenAIProvider:
    """OpenAI-first NLU provider. Visible copy is owned by policy + renderer."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._openai = OpenAIInterpreter(settings)

    def interpret(
        self,
        message: IncomingMessage,
        context: dict[str, object],
        snippets: list[KnowledgeSnippet],
        tools: list[ToolDefinition],
    ) -> NLUResult:
        return self._openai.interpret(message, context, snippets, tools)

    def decide(self, *args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        raise RuntimeError(
            "Legacy decide() is disabled. Use NLU interpreter + "
            "ConversationPolicy + CopyRenderer."
        )
