from __future__ import annotations

from core.adapters.vedruna.tools.rpa_appointments import RPAAppointmentClient
from core.config import Settings


def test_rpa_availability_returns_dry_run_slots() -> None:
    client = RPAAppointmentClient(
        Settings(OPENAI_API_KEY="", DATABASE_URL="", RPA_DRY_RUN=True)
    )
    result = client.search_availability({"clinic": "madre_vedruna"})
    assert result.status == "success"
    assert result.data["dry_run"] is True
    assert result.data["slots"][0]["slot_id"].startswith("dry-madre_vedruna")


def test_rpa_create_is_suppressed_in_dry_run() -> None:
    client = RPAAppointmentClient(
        Settings(OPENAI_API_KEY="", DATABASE_URL="", RPA_DRY_RUN=True)
    )
    result = client.create_appointment({"patient": {"phone": "600111222"}})
    assert result.status == "dry_run"
    assert result.internal_code == "dry_run_write_suppressed"
    assert result.data["arguments"]["patient"]["phone"] == "[redacted_phone]"
