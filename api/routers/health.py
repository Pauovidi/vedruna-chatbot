from __future__ import annotations

from fastapi import APIRouter

from api.dependencies import get_registry, get_store
from core.clients import list_client_ids
from core.config import get_settings
from core.prompts.loader import PromptLoader

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, object]:
    settings = get_settings()
    body = settings.safe_health()
    try:
        store = get_store()
        body["tables_ready"] = store.tables_ready
    except Exception:
        body["tables_ready"] = False
        body["production_ready"] = False
    try:
        PromptLoader().load("default", "webchat")
        body["prompt_loader_ready"] = True
    except Exception:
        body["prompt_loader_ready"] = False
    body["clients_count"] = len(list_client_ids())
    body["tools_count"] = len(get_registry().list())
    body.update(_git_info())
    return body


def _git_info() -> dict[str, str | None]:
    import subprocess

    def run(args: list[str]) -> str | None:
        try:
            completed = subprocess.run(
                args,
                check=True,
                capture_output=True,
                text=True,
                timeout=2,
            )
        except Exception:
            return None
        return completed.stdout.strip() or None

    return {
        "git_sha": run(["git", "rev-parse", "--short", "HEAD"]),
        "git_branch": run(["git", "branch", "--show-current"]),
    }
