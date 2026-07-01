from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from core.config import ROOT_DIR


class PromptBundle(BaseModel):
    base: str
    channel: str
    safety: str
    privacy: str
    tool_policy: str
    client: str
    warnings: list[str] = Field(default_factory=list)

    def system_text(self) -> str:
        parts = [
            self.base,
            self.channel,
            self.safety,
            self.privacy,
            self.tool_policy,
            self.client,
        ]
        return "\n\n".join(part.strip() for part in parts if part.strip())


class PromptLoader:
    def __init__(self, root_dir: Path = ROOT_DIR) -> None:
        self.root_dir = root_dir

    def load(self, client_id: str, channel: str) -> PromptBundle:
        warnings: list[str] = []
        prompts_dir = self.root_dir / "prompts"
        return PromptBundle(
            base=self._read(prompts_dir / "base_agent.md", warnings, required=True),
            channel=self._read_channel(prompts_dir, channel, warnings),
            safety=self._read(prompts_dir / "safety_policy.md", warnings, required=True),
            privacy=self._read(prompts_dir / "privacy_policy.md", warnings, required=True),
            tool_policy=self._read(prompts_dir / "tool_policy.md", warnings, required=True),
            client=self._read(
                self.root_dir / "clients" / client_id / "system_prompt.md",
                warnings,
                required=False,
            ),
            warnings=warnings,
        )

    def _read_channel(self, prompts_dir: Path, channel: str, warnings: list[str]) -> str:
        path = prompts_dir / f"channel_{channel}.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        warnings.append(f"missing_channel_prompt:{channel}")
        fallback = prompts_dir / "channel_whatsapp.md"
        if fallback.exists():
            return fallback.read_text(encoding="utf-8")
        return "Responde de forma breve, clara y segura."

    def _read(self, path: Path, warnings: list[str], *, required: bool) -> str:
        if path.exists():
            return path.read_text(encoding="utf-8")
        warnings.append(f"missing_prompt:{path.name}")
        if required:
            return "Actua de forma breve, clara y segura. No inventes datos."
        return ""
