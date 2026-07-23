from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from core.adapters.vedruna.tools import rpa_appointments
from core.adapters.vedruna.tools.rpa_appointments import (
    RPAAppointmentClient,
    VoiceTransferHandler,
)
from core.config import Settings
from core.conversation.actions import ConversationAction
from core.conversation.policy import reconcile_tool_results
from core.llm.schemas import ToolCallRequest


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_rpa_availability_returns_dry_run_slots() -> None:
    client = RPAAppointmentClient(
        Settings(OPENAI_API_KEY="", DATABASE_URL="", RPA_DRY_RUN=True)
    )
    result = client.search_availability({"clinic": "madre_vedruna"})
    assert result.status == "success"
    assert result.data["dry_run"] is True
    assert result.data["slots"][0]["slot_id"].startswith("dry-madre_vedruna")


def test_rpa_live_reads_can_be_enabled_while_writes_stay_dry_run(monkeypatch) -> None:
    captured: list[str] = []

    def fake_urlopen(req, timeout):
        captured.append(req.full_url)
        return FakeResponse(
            {
                "date": "08/07/2026",
                "dateISO": "2026-07-08",
                "slots": ["12:30"],
            }
        )

    monkeypatch.setattr(rpa_appointments.request, "urlopen", fake_urlopen)
    client = RPAAppointmentClient(
        Settings(
            OPENAI_API_KEY="",
            DATABASE_URL="",
            RPA_DRY_RUN=True,
            RPA_LIVE_READS_ENABLED=True,
        )
    )

    availability = client.search_availability(
        {"clinic": "santa_isabel", "service": "quiropodia"}
    )
    creation = client.create_appointment({"patient": {"phone": "600111222"}})

    assert captured[0].endswith("/appointments/availability/search")
    assert availability.status == "success"
    assert availability.data["dry_run"] is False
    assert availability.data["slots"][0]["time"] == "12:30"
    assert creation.status == "dry_run"
    assert creation.internal_code == "dry_run_write_suppressed"


def test_rpa_find_supports_full_name_without_phone(monkeypatch) -> None:
    captured: list[dict[str, Any]] = []

    def fake_urlopen(req, timeout):
        captured.append(json.loads(req.data.decode()))
        return FakeResponse({"success": True, "appointments": []})

    monkeypatch.setattr(rpa_appointments.request, "urlopen", fake_urlopen)
    client = RPAAppointmentClient(
        Settings(
            OPENAI_API_KEY="",
            DATABASE_URL="",
            RPA_DRY_RUN=True,
            RPA_LIVE_READS_ENABLED=True,
        )
    )

    result = client.find_appointment(
        {
            "patient_first_name": "Lucas",
            "patient_last_names": "Prueba Automatizada",
        }
    )

    assert captured == [{"name": "Lucas Prueba Automatizada"}]
    assert result.internal_code == "rpa_appointment_not_found"


def test_rpa_availability_rejects_closed_day_before_calling_rpa() -> None:
    client = RPAAppointmentClient(
        Settings(OPENAI_API_KEY="", DATABASE_URL="", RPA_DRY_RUN=True)
    )

    result = client.search_availability(
        {"clinic": "madre_vedruna", "date_preference": "monday"}
    )

    assert result.status == "success"
    assert result.data["slots"] == []
    assert result.data["availability_reason"] == "clinic_closed_on_requested_day"
    assert result.data["requested_weekday"] == "lunes"


def test_rpa_availability_dry_run_uses_clinic_open_day() -> None:
    client = RPAAppointmentClient(
        Settings(OPENAI_API_KEY="", DATABASE_URL="", RPA_DRY_RUN=True)
    )

    result = client.search_availability(
        {"clinic": "santa_isabel", "date_preference": "monday"}
    )

    slot_start = datetime.fromisoformat(result.data["slots"][0]["start"])
    assert slot_start.weekday() == 0


def test_rpa_create_is_suppressed_in_dry_run() -> None:
    client = RPAAppointmentClient(
        Settings(OPENAI_API_KEY="", DATABASE_URL="", RPA_DRY_RUN=True)
    )
    result = client.create_appointment({"patient": {"phone": "600111222"}})
    assert result.status == "dry_run"
    assert result.internal_code == "dry_run_write_suppressed"
    assert result.data["arguments"]["patient"]["phone"] == "[redacted_phone]"


def test_rpa_real_availability_normalizes_slots(monkeypatch) -> None:
    captured: list[dict[str, Any]] = []

    def fake_urlopen(req, timeout):
        captured.append({"url": req.full_url, "payload": json.loads(req.data.decode())})
        return FakeResponse(
            {
                "date": "08/07/2026",
                "dateISO": "2026-07-08",
                "dateReadable": "miercoles, 8 de julio",
                "slots": ["12:30"],
            }
        )

    monkeypatch.setattr(rpa_appointments.request, "urlopen", fake_urlopen)
    client = RPAAppointmentClient(
        Settings(OPENAI_API_KEY="", DATABASE_URL="", RPA_DRY_RUN=False)
    )

    result = client.search_availability(
        {"clinic": "santa_isabel", "service": "quiropodia", "limit": 1}
    )

    assert captured[0]["url"].endswith("/appointments/availability/search")
    assert captured[0]["payload"]["preference"] == "todos"
    assert result.status == "success"
    slot = result.data["slots"][0]
    assert slot["slot_id"] == "2026-07-08T12:30"
    assert slot["date"] == "08/07/2026"
    assert slot["time"] == "12:30"
    assert slot["address"]


def test_rpa_real_availability_sends_requested_weekday_date(monkeypatch) -> None:
    captured: list[dict[str, Any]] = []

    def fake_urlopen(req, timeout):
        payload = json.loads(req.data.decode())
        captured.append(payload)
        date_value = payload["date"]
        day, month, year = date_value.split("/")
        return FakeResponse(
            {
                "date": date_value,
                "dateISO": f"{year}-{month}-{day}",
                "slots": ["12:30"],
            }
        )

    monkeypatch.setattr(rpa_appointments.request, "urlopen", fake_urlopen)
    client = RPAAppointmentClient(
        Settings(OPENAI_API_KEY="", DATABASE_URL="", RPA_DRY_RUN=False)
    )

    result = client.search_availability(
        {"clinic": "santa_isabel", "date_preference": "wednesday"}
    )

    assert datetime.strptime(captured[0]["date"], "%d/%m/%Y").weekday() == 2
    assert result.data["slots"]


def test_rpa_real_availability_rejects_slot_on_closed_clinic_day(monkeypatch) -> None:
    def fake_urlopen(req, timeout):
        return FakeResponse(
            {
                "date": "06/07/2026",
                "dateISO": "2026-07-06",
                "slots": ["12:30"],
            }
        )

    monkeypatch.setattr(rpa_appointments.request, "urlopen", fake_urlopen)
    client = RPAAppointmentClient(
        Settings(OPENAI_API_KEY="", DATABASE_URL="", RPA_DRY_RUN=False)
    )

    result = client.search_availability(
        {"clinic": "madre_vedruna", "service": "podologia"}
    )

    assert result.status == "success"
    assert result.data["slots"] == []
    assert result.data["availability_reason"] == "clinic_closed_on_returned_day"


def test_rpa_real_create_success_allows_confirmation(monkeypatch) -> None:
    captured: list[dict[str, Any]] = []

    def fake_urlopen(req, timeout):
        captured.append(json.loads(req.data.decode()))
        return FakeResponse(
            {"success": True, "message": "Cita creada: Ana Perez el 10/07/2026 a las 16:00"}
        )

    monkeypatch.setattr(rpa_appointments.request, "urlopen", fake_urlopen)
    client = RPAAppointmentClient(
        Settings(OPENAI_API_KEY="", DATABASE_URL="", RPA_DRY_RUN=False)
    )
    result = client.create_appointment(
        {
            "clinic": "santa_isabel",
            "service": "quiropodia",
            "selected_slot": {
                "slot_id": "2026-07-10T16:00",
                "date": "10/07/2026",
                "dateISO": "2026-07-10",
                "time": "16:00",
            },
            "patient": {
                "first_name": "Ana",
                "last_names": "Perez",
                "phone": "600000003",
            },
            "consultation_reason": "dolor en el talon",
            "agenda_title": "cita IA Ana Perez 600000003 dolor en el talon",
        }
    )
    action = ConversationAction(
        action_type="call_tool",
        reply_intent="create_appointment",
        reply_key="vedruna_creating_appointment",
        requires_tool=True,
        tool_name="rpa_create_appointment",
        metadata={"vedruna_flow": "create_appointment"},
    )

    reconciled = reconcile_tool_results(action, [result])

    assert result.status == "success"
    assert result.data["ok"] is True
    assert result.data["dry_run"] is False
    assert result.data["reminder"]["template"] == "appointment_reminder_24h"
    assert captured[0]["observaciones"] == (
        "Ana Perez 600000003 dolor en el talon"
    )
    assert reconciled.reply_key == "vedruna_confirm_appointment"


def test_rpa_real_create_failure_blocks_confirmation(monkeypatch) -> None:
    def fake_urlopen(req, timeout):
        return FakeResponse({"success": False, "message": "No disponible"})

    monkeypatch.setattr(rpa_appointments.request, "urlopen", fake_urlopen)
    client = RPAAppointmentClient(
        Settings(OPENAI_API_KEY="", DATABASE_URL="", RPA_DRY_RUN=False)
    )
    result = client.create_appointment(
        {
            "clinic": "santa_isabel",
            "service": "quiropodia",
            "selected_slot": {
                "date": "10/07/2026",
                "dateISO": "2026-07-10",
                "time": "16:00",
            },
            "patient": {
                "first_name": "Ana",
                "last_names": "Perez",
                "phone": "600000003",
            },
        }
    )

    assert result.status == "failed"
    assert result.data["success"] is False


def test_rpa_cancel_and_reschedule_send_idcita(monkeypatch) -> None:
    captured: list[dict[str, Any]] = []

    def fake_urlopen(req, timeout):
        captured.append({"url": req.full_url, "payload": json.loads(req.data.decode())})
        return FakeResponse({"success": True, "message": "ok"})

    monkeypatch.setattr(rpa_appointments.request, "urlopen", fake_urlopen)
    client = RPAAppointmentClient(
        Settings(OPENAI_API_KEY="", DATABASE_URL="", RPA_DRY_RUN=False)
    )

    client.cancel_appointment({"idCita": "52549", "phone": "600000001"})
    client.reschedule_appointment(
        {
            "idCita": "52550",
            "name": "Maria Prueba",
            "phone": "600000002",
            "service": "estudio_biomecanico",
            "new_slot": {
                "date": "10/07/2026",
                "dateISO": "2026-07-10",
                "time": "15:30",
            },
        }
    )

    assert captured[0]["payload"] == {"idCita": "52549", "phone": "600000001"}
    assert captured[1]["payload"]["idCita"] == "52550"
    assert captured[1]["payload"]["type"] == "estudio"


def test_rpa_mutua_mapping_sanitas_and_catalana_occident(monkeypatch) -> None:
    captured: list[dict[str, Any]] = []

    def fake_urlopen(req, timeout):
        captured.append(json.loads(req.data.decode()))
        return FakeResponse({"success": True, "message": "ok"})

    monkeypatch.setattr(rpa_appointments.request, "urlopen", fake_urlopen)
    client = RPAAppointmentClient(
        Settings(OPENAI_API_KEY="", DATABASE_URL="", RPA_DRY_RUN=False)
    )
    base = {
        "clinic": "madre_vedruna",
        "service": "podologia",
        "selected_slot": {
            "date": "10/07/2026",
            "dateISO": "2026-07-10",
            "time": "16:00",
        },
        "patient": {"first_name": "Lucas", "last_names": "Prueba", "phone": "600000005"},
        "insurance_type": "seguro",
    }

    client.create_appointment({**base, "insurance_provider": "sanitas"})
    client.create_appointment({**base, "insurance_provider": "catalana_occident"})

    assert captured[0]["idMutua"] == 1
    assert captured[1]["idMutua"] == 12


def test_rpa_date_resolves_relative_and_next_week_preferences(monkeypatch) -> None:
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 7, 23, 10, 0, tzinfo=tz)

    monkeypatch.setattr(rpa_appointments, "datetime", FixedDateTime)

    assert rpa_appointments._rpa_date("relative_tomorrow") == "24/07/2026"
    assert rpa_appointments._rpa_date("relative_day_after_tomorrow") == "25/07/2026"
    assert rpa_appointments._rpa_date("next:thursday") == "30/07/2026"
    assert rpa_appointments._rpa_date("next_week:monday") == "27/07/2026"


def test_rpa_find_infers_clinic_from_disjoint_open_weekday() -> None:
    appointment = rpa_appointments._normalize_appointment(
        {
            "idCita": "test-1",
            "date": "2026-08-19",
            "time": "10:00",
        },
        {},
    )

    assert appointment["clinic"] == "santa_isabel"
    assert appointment["address"] == (
        "Avenida Santa Isabel numero 82, local, 50016 Zaragoza"
    )


def test_voice_transfer_disabled_does_not_call_twilio() -> None:
    handler = VoiceTransferHandler(
        Settings(OPENAI_API_KEY="", DATABASE_URL="", VOICE_TRANSFER_ENABLED=False)
    )
    result = handler.execute(
        ToolCallRequest(
            name="voice_transfer_call",
            arguments={"call_sid": "CA1", "phone_number": "976582768"},
        ),
        {},
    )

    assert result.status == "success"
    assert result.data["transfer_enabled"] is False
    assert result.data["real_transfer_executed"] is False


def test_voice_transfer_enabled_uses_twilio_rest_with_mock(monkeypatch) -> None:
    captured: list[str] = []

    def fake_urlopen(req, timeout):
        captured.append(req.full_url)
        return FakeResponse({"sid": "CA1"})

    monkeypatch.setattr(rpa_appointments.request, "urlopen", fake_urlopen)
    handler = VoiceTransferHandler(
        Settings(
            OPENAI_API_KEY="",
            DATABASE_URL="",
            VOICE_TRANSFER_ENABLED=True,
            TWILIO_ACCOUNT_SID="AC-test",
            TWILIO_AUTH_TOKEN="token-test",
        )
    )

    result = handler.execute(
        ToolCallRequest(
            name="voice_transfer_call",
            arguments={"call_sid": "CA1", "phone_number": "976582768"},
        ),
        {},
    )

    assert result.status == "success"
    assert result.data["real_transfer_executed"] is True
    assert captured[0].endswith("/Calls/CA1.json")
