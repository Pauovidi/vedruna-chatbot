from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/webhooks")


@router.post("/whatsapp-stub")
def whatsapp_stub(payload: dict[str, object]) -> dict[str, object]:
    return {"accepted": True, "mode": "stub", "payload_keys": sorted(payload.keys())}
