from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.config import ROOT_DIR


@dataclass(frozen=True)
class Rule:
    name: str
    pattern: str
    allowed_paths: tuple[str, ...] = ()


RULES = (
    Rule(
        name="legacy_conversation_decision",
        pattern="Conversation" + "Decision",
        allowed_paths=("tests/",),
    ),
    Rule(
        name="visible_reply_assignment",
        pattern="reply_text" + "=",
        allowed_paths=(
            "core/conversation/orchestrator.py",
            "tests/",
        ),
    ),
    Rule(
        name="nlu_reply_text_field",
        pattern="reply" + "Text",
        allowed_paths=("tests/", "docs/"),
    ),
    Rule(
        name="nlu_bot_reply_field",
        pattern="bot" + "Reply",
        allowed_paths=("tests/", "docs/"),
    ),
    Rule(
        name="nlu_visible_text_field",
        pattern="visible" + "Text",
        allowed_paths=("tests/", "docs/"),
    ),
    Rule(
        name="direct_channel_send",
        pattern="." + "send(",
        allowed_paths=(
            "core/outbox/",
            "core/conversation/orchestrator.py",
            "tests/",
        ),
    ),
    Rule(
        name="twilio_direct_send",
        pattern="messages" + ".create",
        allowed_paths=("tests/",),
    ),
    Rule(
        name="scheduled_direct_send",
        pattern="send_" + "scheduled",
        allowed_paths=("tests/",),
    ),
    Rule(
        name="critical_tool_write_outside_policy",
        pattern="confirm_" + "cancellation",
        allowed_paths=(
            "core/tools/builtin_tools.py",
            "tests/",
            "README_TOOLS.md",
        ),
    ),
)

SKIP_DIRS = {
    ".git",
    ".venv",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "devestial_conversation_core_openai.egg-info",
    "venv",
}


def _iter_files(root_dir: Path) -> list[Path]:
    files: list[Path] = []
    for path in root_dir.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix in {".py", ".md", ".yaml", ".yml"}:
            files.append(path)
    return files


def _is_allowed(relative: str, rule: Rule) -> bool:
    return any(
        relative == allowed or relative.startswith(allowed)
        for allowed in rule.allowed_paths
    )


def check_conversation_authority(root_dir: Path = ROOT_DIR) -> list[str]:
    violations: list[str] = []
    for path in _iter_files(root_dir):
        relative = path.relative_to(root_dir).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        for rule in RULES:
            if rule.pattern in text and not _is_allowed(relative, rule):
                violations.append(f"{rule.name}: {relative}")
    return violations


def main() -> None:
    violations = check_conversation_authority()
    if violations:
        print("conversation authority violations:")
        for violation in violations:
            print(f"- {violation}")
        raise SystemExit(1)
    print("conversation authority checks passed")


if __name__ == "__main__":
    main()
