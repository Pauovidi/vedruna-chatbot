from __future__ import annotations

from pathlib import Path

import yaml

from core.config import ROOT_DIR
from core.tools.schemas import ToolDefinition


def list_client_ids(root_dir: Path = ROOT_DIR) -> list[str]:
    clients_dir = root_dir / "clients"
    if not clients_dir.exists():
        return []
    return sorted(path.name for path in clients_dir.iterdir() if path.is_dir())


def load_client_tools(root_dir: Path = ROOT_DIR) -> list[ToolDefinition]:
    tools: list[ToolDefinition] = []
    for client_id in list_client_ids(root_dir):
        path = root_dir / "clients" / client_id / "tools.yaml"
        if not path.exists():
            continue
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for item in payload.get("tools", []):
            tools.append(ToolDefinition.model_validate(item))
    return tools
