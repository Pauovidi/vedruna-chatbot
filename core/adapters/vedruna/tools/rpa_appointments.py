from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib import request
from urllib.error import URLError

from core.adapters.vedruna.domain_schema import Clinic, clinic_address
from core.config import Settings
from core.llm.schemas import ToolCallRequest, ToolResult
from core.observability.redaction import redact_payload
from core.tools.schemas import ToolHandler


class RPAAppointmentsHandler:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()

    def execute(self, request: ToolCallRequest, context: dict[str, Any]) -> ToolResult:
        del context
        client = RPAAppointmentClient(self.settings)
        return client.execute(request.name, request.arguments)


class VoiceTransferHandler:
    def execute(self, request: ToolCallRequest, context: dict[str, Any]) -> ToolResult:
        del context
        return ToolResult(
            name=request.name,
            status="success",
            user_safe_summary="Transferencia de voz preparada.",
            data=redact_payload(request.arguments),
        )


class RPAAppointmentClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def execute(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        if name == "rpa_search_availability":
            return self.search_availability(arguments)
        if name == "rpa_create_appointment":
            return self.create_appointment(arguments)
        if name == "rpa_find_appointment":
            return self.find_appointment(arguments)
        if name == "rpa_cancel_appointment":
            return self.cancel_appointment(arguments)
        if name == "rpa_reschedule_appointment":
            return self.reschedule_appointment(arguments)
        if name == "schedule_reminder":
            return self.schedule_reminder(arguments)
        return ToolResult(
            name=name,
            status="failed",
            user_safe_summary="Operacion RPA no reconocida.",
            internal_code="unknown_vedruna_rpa_tool",
        )

    def search_availability(self, arguments: dict[str, Any]) -> ToolResult:
        if self.settings.rpa_dry_run:
            clinic = str(arguments.get("clinic") or Clinic.MADRE_VEDRUNA.value)
            slots = _fixture_slots(clinic)
            return ToolResult(
                name="rpa_search_availability",
                status="success",
                user_safe_summary="Disponibilidad simulada para pruebas.",
                data={"ok": True, "dry_run": True, "slots": slots},
            )
        return self._post("rpa_search_availability", "/availability/search", arguments)

    def create_appointment(self, arguments: dict[str, Any]) -> ToolResult:
        if self.settings.rpa_dry_run:
            return ToolResult(
                name="rpa_create_appointment",
                status="dry_run",
                user_safe_summary="Creacion suprimida por RPA_DRY_RUN.",
                internal_code="dry_run_write_suppressed",
                data={"ok": False, "dry_run": True, "arguments": redact_payload(arguments)},
            )
        return self._post("rpa_create_appointment", "/appointments", arguments)

    def find_appointment(self, arguments: dict[str, Any]) -> ToolResult:
        if self.settings.rpa_dry_run:
            clinic = str(arguments.get("clinic") or Clinic.MADRE_VEDRUNA.value)
            return ToolResult(
                name="rpa_find_appointment",
                status="success",
                user_safe_summary="Cita simulada encontrada para pruebas.",
                data={
                    "ok": True,
                    "dry_run": True,
                    "appointment": {
                        "appointment_id": "dry-apt-1",
                        "start": "2026-07-07T10:00:00+02:00",
                        "end": "2026-07-07T10:20:00+02:00",
                        "clinic": clinic,
                        "address": clinic_address(clinic),
                    },
                },
            )
        return self._post("rpa_find_appointment", "/appointments/find", arguments)

    def cancel_appointment(self, arguments: dict[str, Any]) -> ToolResult:
        if self.settings.rpa_dry_run:
            return ToolResult(
                name="rpa_cancel_appointment",
                status="dry_run",
                user_safe_summary="Cancelacion suprimida por RPA_DRY_RUN.",
                internal_code="dry_run_write_suppressed",
                data={"ok": False, "dry_run": True, "arguments": redact_payload(arguments)},
            )
        return self._post("rpa_cancel_appointment", "/appointments/cancel", arguments)

    def reschedule_appointment(self, arguments: dict[str, Any]) -> ToolResult:
        if self.settings.rpa_dry_run:
            return ToolResult(
                name="rpa_reschedule_appointment",
                status="dry_run",
                user_safe_summary="Reagendado suprimido por RPA_DRY_RUN.",
                internal_code="dry_run_write_suppressed",
                data={"ok": False, "dry_run": True, "arguments": redact_payload(arguments)},
            )
        return self._post("rpa_reschedule_appointment", "/appointments/reschedule", arguments)

    def schedule_reminder(self, arguments: dict[str, Any]) -> ToolResult:
        if self.settings.rpa_dry_run:
            return ToolResult(
                name="schedule_reminder",
                status="dry_run",
                user_safe_summary="Recordatorio preparado en modo prueba.",
                data={"ok": False, "dry_run": True, "arguments": redact_payload(arguments)},
            )
        return self._post("schedule_reminder", "/reminders", arguments)

    def _post(self, name: str, path: str, payload: dict[str, Any]) -> ToolResult:
        base_url = self.settings.rpa_base_url.rstrip("/")
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.settings.rpa_api_key:
            headers["Authorization"] = f"Bearer {self.settings.rpa_api_key}"
        http_request = request.Request(
            f"{base_url}{path}",
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            timeout = self.settings.rpa_timeout_ms / 1000
            with request.urlopen(http_request, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8") or "{}")
        except (OSError, URLError, TimeoutError, json.JSONDecodeError):
            return ToolResult(
                name=name,
                status="failed",
                user_safe_summary="La RPA no ha respondido correctamente.",
                internal_code="rpa_http_error",
            )
        if data.get("ok") is True:
            return ToolResult(
                name=name,
                status="success",
                user_safe_summary="Operacion RPA completada.",
                data=redact_payload(data),
            )
        return ToolResult(
            name=name,
            status="failed",
            user_safe_summary="La RPA no ha confirmado la operacion.",
            internal_code=str(data.get("error_code") or "rpa_not_ok"),
            data=redact_payload(data),
        )


def get_vedruna_tool_handlers(settings: Settings | None = None) -> dict[str, ToolHandler]:
    rpa_handler = RPAAppointmentsHandler(settings)
    return {
        "rpa_appointments": rpa_handler,
        "voice_transfer": VoiceTransferHandler(),
    }


def _fixture_slots(clinic: str) -> list[dict[str, str]]:
    start = datetime(2026, 7, 7, 10, 0, tzinfo=timezone(timedelta(hours=2)))
    if clinic == Clinic.SANTA_ISABEL.value:
        start = datetime(2026, 7, 8, 16, 0, tzinfo=timezone(timedelta(hours=2)))
    return [
        {
            "slot_id": f"dry-{clinic}-1",
            "start": start.isoformat(),
            "end": (start + timedelta(minutes=20)).isoformat(),
            "clinic": clinic,
            "address": clinic_address(clinic),
        },
        {
            "slot_id": f"dry-{clinic}-2",
            "start": (start + timedelta(minutes=20)).isoformat(),
            "end": (start + timedelta(minutes=40)).isoformat(),
            "clinic": clinic,
            "address": clinic_address(clinic),
        },
    ]


def rpa_dry_run_from_env() -> bool:
    return os.environ.get("RPA_DRY_RUN", "true").lower() not in {"0", "false", "no"}
