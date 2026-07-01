from __future__ import annotations

from fastapi import APIRouter

from api.dependencies import get_events, get_registry
from core.observability.events import Event
from core.tools.schemas import ToolDefinition

router = APIRouter()


@router.get("/tools", response_model=list[ToolDefinition])
def tools() -> list[ToolDefinition]:
    return get_registry().list()


@router.get("/conversations/{conversation_id}/events", response_model=list[Event])
def events(conversation_id: str) -> list[Event]:
    return get_events().list_for(conversation_id)
