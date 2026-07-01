from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.dependencies import get_orchestrator
from core.clients import list_client_ids
from core.llm.schemas import ChatTurnResult, IncomingMessage

router = APIRouter()


@router.post("/chat/test-turn", response_model=ChatTurnResult)
def test_turn(message: IncomingMessage) -> ChatTurnResult:
    return get_orchestrator().handle_turn(message)


@router.post("/clients/{client_id}/chat", response_model=ChatTurnResult)
def client_chat(client_id: str, message: IncomingMessage) -> ChatTurnResult:
    if client_id not in list_client_ids():
        raise HTTPException(status_code=404, detail="Unknown client_id")
    normalized = message.model_copy(update={"client_id": client_id})
    return get_orchestrator().handle_turn(normalized)


@router.get("/clients")
def clients() -> dict[str, list[str]]:
    return {"clients": list_client_ids()}
