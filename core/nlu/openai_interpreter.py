from __future__ import annotations

import json

from core.config import Settings
from core.knowledge.schemas import KnowledgeSnippet
from core.llm.schemas import IncomingMessage
from core.nlu.schemas import NLUResult
from core.prompts.loader import PromptLoader
from core.tools.schemas import ToolDefinition


class OpenAIInterpreter:
    def __init__(
        self,
        settings: Settings,
        prompt_loader: PromptLoader | None = None,
    ) -> None:
        self.settings = settings
        self.prompt_loader = prompt_loader or PromptLoader()

    def interpret(
        self,
        message: IncomingMessage,
        context: dict[str, object],
        snippets: list[KnowledgeSnippet],
        tools: list[ToolDefinition],
    ) -> NLUResult:
        if not self.settings.openai_api_key:
            raise RuntimeError("OpenAI API key is not configured")

        from openai import OpenAI

        bundle = self.prompt_loader.load(message.client_id, message.channel)
        payload = {
            "message": message.model_dump(mode="json"),
            "context": context,
            "knowledge_snippets": [
                {
                    "id": snippet.id,
                    "title": snippet.title,
                    "snippet": snippet.snippet,
                    "source_id": snippet.source_id,
                }
                for snippet in snippets
            ],
            "available_tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "risk_level": tool.risk_level,
                    "required_confirmation": tool.required_confirmation,
                    "required_flags": tool.required_flags,
                    "allowed_channels": tool.allowed_channels,
                }
                for tool in tools
            ],
            "prompt_warnings": bundle.warnings,
        }
        client = OpenAI(
            api_key=self.settings.openai_api_key,
            timeout=self.settings.openai_timeout_seconds,
        )
        response = client.responses.create(
            model=self.settings.openai_model,
            temperature=self.settings.openai_temperature,
            input=[
                {"role": "system", "content": bundle.system_text()},
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False),
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "nlu_result",
                    "schema": NLUResult.model_json_schema(),
                    "strict": True,
                }
            },
        )
        return NLUResult.model_validate_json(response.output_text)
