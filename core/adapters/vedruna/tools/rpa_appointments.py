from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timedelta
from typing import Any
from urllib import request
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from core.adapters.vedruna.domain_schema import (
    Clinic,
    clinic_address,
    clinic_is_open_on_weekday,
    weekday_index,
    weekday_name_es,
)
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
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()

    def execute(self, request: ToolCallRequest, context: dict[str, Any]) -> ToolResult:
        del context
        if not self.settings.voice_transfer_enabled:
            return ToolResult(
                name=request.name,
                status="success",
                user_safe_summary="Transferencia real desactivada por configuracion.",
                data={
                    "ok": True,
                    "transfer_enabled": False,
                    "real_transfer_executed": False,
                    "arguments": redact_payload(request.arguments),
                },
            )
        call_sid = request.arguments.get("call_sid")
        if not call_sid:
            return ToolResult(
                name=request.name,
                status="failed",
                user_safe_summary="No se puede transferir sin identificador de llamada.",
                internal_code="missing_call_sid",
            )
        phone_number = request.arguments.get("phone_number")
        if (
            not self.settings.twilio_account_sid
            or not self.settings.twilio_auth_token
            or not phone_number
        ):
            return ToolResult(
                name=request.name,
                status="failed",
                user_safe_summary="Faltan credenciales o telefono para transferencia Twilio.",
                internal_code="twilio_transfer_not_configured",
            )
        if not self._execute_twilio_transfer(str(call_sid), str(phone_number)):
            return ToolResult(
                name=request.name,
                status="failed",
                user_safe_summary="Twilio no ha confirmado la transferencia.",
                internal_code="twilio_transfer_failed",
            )
        return ToolResult(
            name=request.name,
            status="success",
            user_safe_summary="Transferencia de voz solicitada a Twilio.",
            data={
                "ok": True,
                "transfer_enabled": True,
                "real_transfer_executed": True,
                "arguments": redact_payload(request.arguments),
            },
        )

    def _execute_twilio_transfer(self, call_sid: str, phone_number: str) -> bool:
        account_sid = self.settings.twilio_account_sid or ""
        auth_token = self.settings.twilio_auth_token or ""
        twiml = f"<Response><Dial>{phone_number}</Dial></Response>"
        body = urlencode({"Twiml": twiml}).encode("utf-8")
        url = (
            "https://api.twilio.com/2010-04-01/Accounts/"
            f"{account_sid}/Calls/{call_sid}.json"
        )
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": "Basic "
            + base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode("ascii"),
        }
        http_request = request.Request(url, data=body, headers=headers, method="POST")
        try:
            timeout = self.settings.rpa_timeout_ms / 1000
            with request.urlopen(http_request, timeout=timeout) as response:
                response.read()
            return True
        except (HTTPError, OSError, URLError, TimeoutError):
            return False


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
        clinic = str(arguments.get("clinic") or Clinic.MADRE_VEDRUNA.value)
        requested_weekday = _requested_weekday(arguments)
        if (
            requested_weekday is not None
            and not clinic_is_open_on_weekday(clinic, requested_weekday)
        ):
            return _availability_without_slots(
                clinic=clinic,
                dry_run=self.settings.rpa_dry_run,
                reason="clinic_closed_on_requested_day",
                requested_weekday=requested_weekday,
            )
        if self.settings.rpa_dry_run and not self.settings.rpa_live_reads_enabled:
            slots = _fixture_slots(clinic, arguments)
            return ToolResult(
                name="rpa_search_availability",
                status="success",
                user_safe_summary="Disponibilidad simulada para pruebas.",
                data={
                    "ok": True,
                    "dry_run": True,
                    "slots": slots,
                    "clinic": clinic,
                },
            )
        payload = _availability_payload(arguments)
        data = self._post_json("/appointments/availability/search", payload)
        if data is None:
            return _rpa_http_error("rpa_search_availability")
        return _availability_result(arguments, data)

    def create_appointment(self, arguments: dict[str, Any]) -> ToolResult:
        if self.settings.rpa_dry_run:
            return ToolResult(
                name="rpa_create_appointment",
                status="dry_run",
                user_safe_summary="Creacion suprimida por RPA_DRY_RUN.",
                internal_code="dry_run_write_suppressed",
                data={"ok": False, "dry_run": True, "arguments": redact_payload(arguments)},
            )
        payload = _create_payload(arguments)
        if not payload:
            return _rpa_missing_fields("rpa_create_appointment")
        data = self._post_json("/appointments/create", payload)
        if data is None:
            return _rpa_http_error("rpa_create_appointment")
        return _create_result(arguments, data)

    def find_appointment(self, arguments: dict[str, Any]) -> ToolResult:
        if self.settings.rpa_dry_run and not self.settings.rpa_live_reads_enabled:
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
        payload = _find_payload(arguments)
        if not payload:
            return _rpa_missing_fields("rpa_find_appointment")
        data = self._post_json("/appointments/find", payload)
        if data is None:
            return _rpa_http_error("rpa_find_appointment")
        return _find_result(arguments, data)

    def cancel_appointment(self, arguments: dict[str, Any]) -> ToolResult:
        if self.settings.rpa_dry_run:
            return ToolResult(
                name="rpa_cancel_appointment",
                status="dry_run",
                user_safe_summary="Cancelacion suprimida por RPA_DRY_RUN.",
                internal_code="dry_run_write_suppressed",
                data={"ok": False, "dry_run": True, "arguments": redact_payload(arguments)},
            )
        payload = _cancel_payload(arguments)
        if not payload:
            return _rpa_missing_fields("rpa_cancel_appointment")
        data = self._post_json("/appointments/cancel", payload)
        if data is None:
            return _rpa_http_error("rpa_cancel_appointment")
        return _write_result("rpa_cancel_appointment", arguments, data)

    def reschedule_appointment(self, arguments: dict[str, Any]) -> ToolResult:
        if self.settings.rpa_dry_run:
            return ToolResult(
                name="rpa_reschedule_appointment",
                status="dry_run",
                user_safe_summary="Reagendado suprimido por RPA_DRY_RUN.",
                internal_code="dry_run_write_suppressed",
                data={"ok": False, "dry_run": True, "arguments": redact_payload(arguments)},
            )
        payload = _reschedule_payload(arguments)
        if not payload:
            return _rpa_missing_fields("rpa_reschedule_appointment")
        data = self._post_json("/appointments/reschedule", payload)
        if data is None:
            return _rpa_http_error("rpa_reschedule_appointment")
        return _write_result("rpa_reschedule_appointment", arguments, data)

    def schedule_reminder(self, arguments: dict[str, Any]) -> ToolResult:
        if self.settings.rpa_dry_run:
            return ToolResult(
                name="schedule_reminder",
                status="dry_run",
                user_safe_summary="Recordatorio preparado en modo prueba.",
                data={"ok": False, "dry_run": True, "arguments": redact_payload(arguments)},
            )
        return self._post("schedule_reminder", "/reminders", arguments)

    def health(self) -> ToolResult:
        base_url = self.settings.rpa_base_url.rstrip("/")
        http_request = request.Request(f"{base_url}/health", method="GET")
        try:
            timeout = self.settings.rpa_timeout_ms / 1000
            with request.urlopen(http_request, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8") or "{}")
        except (OSError, URLError, TimeoutError, json.JSONDecodeError):
            return _rpa_http_error("rpa_health")
        return ToolResult(
            name="rpa_health",
            status="success",
            user_safe_summary="Health RPA disponible.",
            data=redact_payload(data),
        )

    def _post(self, name: str, path: str, payload: dict[str, Any]) -> ToolResult:
        data = self._post_json(path, payload)
        if data is None:
            return _rpa_http_error(name)
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

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any] | None:
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
                return json.loads(response.read().decode("utf-8") or "{}")
        except (HTTPError, OSError, URLError, TimeoutError, json.JSONDecodeError):
            return None


def get_vedruna_tool_handlers(settings: Settings | None = None) -> dict[str, ToolHandler]:
    rpa_handler = RPAAppointmentsHandler(settings)
    return {
        "rpa_appointments": rpa_handler,
        "voice_transfer": VoiceTransferHandler(settings),
    }


def _fixture_slots(clinic: str, arguments: dict[str, Any]) -> list[dict[str, str]]:
    requested_weekday = _requested_weekday(arguments)
    start_date = _next_open_date(clinic, requested_weekday)
    start_hour = 16 if clinic == Clinic.SANTA_ISABEL.value else 10
    start = datetime(
        start_date.year,
        start_date.month,
        start_date.day,
        start_hour,
        0,
        tzinfo=ZoneInfo("Europe/Madrid"),
    )
    service = str(arguments.get("service") or "podologia")
    return [
        {
            "slot_id": f"dry-{clinic}-1",
            "date": start.strftime("%d/%m/%Y"),
            "dateISO": start.strftime("%Y-%m-%d"),
            "time": start.strftime("%H:%M"),
            "start": start.isoformat(),
            "end": (start + timedelta(minutes=20)).isoformat(),
            "clinic": clinic,
            "service": service,
            "address": clinic_address(clinic),
        },
        {
            "slot_id": f"dry-{clinic}-2",
            "date": (start + timedelta(minutes=20)).strftime("%d/%m/%Y"),
            "dateISO": (start + timedelta(minutes=20)).strftime("%Y-%m-%d"),
            "time": (start + timedelta(minutes=20)).strftime("%H:%M"),
            "start": (start + timedelta(minutes=20)).isoformat(),
            "end": (start + timedelta(minutes=40)).isoformat(),
            "clinic": clinic,
            "service": service,
            "address": clinic_address(clinic),
        },
    ]


def _availability_payload(arguments: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "preference": _rpa_preference(arguments.get("time_preference")),
        "limit": int(arguments.get("limit") or 4),
        "emergencia": bool(arguments.get("emergencia") or arguments.get("urgent")),
    }
    date_value = _rpa_date(arguments.get("date") or arguments.get("date_preference"))
    if date_value:
        payload["date"] = date_value
    return payload


def _availability_result(arguments: dict[str, Any], data: dict[str, Any]) -> ToolResult:
    raw_slots = data.get("slots")
    if not isinstance(raw_slots, list):
        return _rpa_not_ok("rpa_search_availability", data)
    clinic = str(arguments.get("clinic") or Clinic.MADRE_VEDRUNA.value)
    service = str(arguments.get("service") or "podologia")
    date_value = str(data.get("date") or "")
    date_iso = str(data.get("dateISO") or _date_to_iso(date_value) or "")
    normalized_slots = [
        _slot_from_real_response(
            slot_time=str(slot_time),
            date=date_value,
            date_iso=date_iso,
            clinic=clinic,
            service=service,
        )
        for slot_time in raw_slots
    ]
    valid_slots = [
        slot
        for slot in normalized_slots
        if _slot_is_on_clinic_open_day(slot, clinic)
    ]
    if normalized_slots and not valid_slots:
        return _availability_without_slots(
            clinic=clinic,
            dry_run=False,
            reason="clinic_closed_on_returned_day",
            requested_weekday=_requested_weekday(arguments),
        )
    return ToolResult(
        name="rpa_search_availability",
        status="success",
        user_safe_summary="Disponibilidad RPA normalizada.",
        data={
            "ok": True,
            "dry_run": False,
            "date": date_value,
            "dateISO": date_iso,
            "dateReadable": data.get("dateReadable"),
            "slots": valid_slots,
        },
    )


def _create_payload(arguments: dict[str, Any]) -> dict[str, Any] | None:
    slot = _selected_slot(arguments)
    patient = arguments.get("patient") if isinstance(arguments.get("patient"), dict) else {}
    phone = str(arguments.get("phone") or patient.get("phone") or "").strip()
    name = _full_name(arguments, patient)
    date_value = _rpa_date(arguments.get("date") or slot.get("date") or slot.get("dateISO"))
    time_value = str(arguments.get("time") or slot.get("time") or "").strip()
    if not phone or not name or not date_value or not time_value:
        return None
    payload: dict[str, Any] = {
        "is_new_patient": bool(arguments.get("is_new_patient", True)),
        "name": name,
        "phone": phone,
        "date": date_value,
        "time": time_value,
        "type": _rpa_service_type(str(arguments.get("service") or slot.get("service") or "")),
    }
    observations = _rpa_observations(arguments, name, phone)
    if observations:
        # APClinic's RPA adds the "CITA IA - " prefix when it writes this field.
        payload["observaciones"] = observations
    id_mutua = _mutua_id(arguments.get("insurance_provider"))
    if id_mutua is not None and arguments.get("insurance_type") == "seguro":
        payload["mutua"] = True
        payload["idMutua"] = id_mutua
    return payload


def _rpa_observations(arguments: dict[str, Any], name: str, phone: str) -> str:
    agenda_title = str(arguments.get("agenda_title") or "").strip()
    prefix = "cita IA "
    if agenda_title.casefold().startswith(prefix.casefold()):
        return agenda_title[len(prefix) :].strip()
    reason = str(arguments.get("consultation_reason") or "").strip()
    return " ".join(part for part in (name, phone, reason) if part).strip()


def _create_result(arguments: dict[str, Any], data: dict[str, Any]) -> ToolResult:
    if data.get("success") is not True:
        return _rpa_not_ok("rpa_create_appointment", data)
    slot = _selected_slot(arguments)
    start = _start_iso(slot.get("dateISO") or slot.get("date"), slot.get("time"))
    normalized = {
        "ok": True,
        "success": True,
        "dry_run": False,
        "appointment_id": data.get("appointment_id") or data.get("idCita"),
        "date": slot.get("date"),
        "time": slot.get("time"),
        "start": start,
        "clinic": arguments.get("clinic"),
        "address": clinic_address(str(arguments.get("clinic") or "")),
        "message": data.get("message"),
        "reminder": _reminder(start),
    }
    return ToolResult(
        name="rpa_create_appointment",
        status="success",
        user_safe_summary="Cita creada por RPA.",
        data=redact_payload(normalized),
    )


def _find_payload(arguments: dict[str, Any]) -> dict[str, Any] | None:
    phone = str(arguments.get("phone") or arguments.get("patient_phone") or "").strip()
    patient = arguments.get("patient")
    if not isinstance(patient, dict):
        patient = {}
    name = _full_name(arguments, patient)
    if not phone and not name:
        return None
    payload: dict[str, Any] = {}
    if phone:
        payload["phone"] = phone
    if name:
        payload["name"] = name
    date_value = _rpa_date(arguments.get("date") or arguments.get("date_preference"))
    if date_value:
        payload["date"] = date_value
    if arguments.get("time"):
        payload["time"] = str(arguments["time"])
    return payload


def _find_result(arguments: dict[str, Any], data: dict[str, Any]) -> ToolResult:
    if data.get("success") is not True or not isinstance(data.get("appointments"), list):
        return _rpa_not_ok("rpa_find_appointment", data)
    appointments = [_normalize_appointment(item, arguments) for item in data["appointments"]]
    if not appointments:
        return ToolResult(
            name="rpa_find_appointment",
            status="failed",
            user_safe_summary="No se ha encontrado ninguna cita con esos datos.",
            internal_code="rpa_appointment_not_found",
            data={"ok": False, "dry_run": False, "appointments": []},
        )
    return ToolResult(
        name="rpa_find_appointment",
        status="success",
        user_safe_summary="Cita RPA encontrada.",
        data={
            "ok": True,
            "dry_run": False,
            "appointment": appointments[0] if appointments else None,
            "appointments": appointments,
        },
    )


def _cancel_payload(arguments: dict[str, Any]) -> dict[str, Any] | None:
    appointment_id = str(
        arguments.get("idCita") or arguments.get("appointment_id") or ""
    ).strip()
    phone = str(arguments.get("phone") or arguments.get("patient_phone") or "").strip()
    if not appointment_id or not phone:
        return None
    return {"idCita": appointment_id, "phone": phone}


def _reschedule_payload(arguments: dict[str, Any]) -> dict[str, Any] | None:
    slot = _selected_slot(arguments, slot_key="new_slot")
    appointment_id = str(
        arguments.get("idCita") or arguments.get("appointment_id") or ""
    ).strip()
    phone = str(arguments.get("phone") or arguments.get("patient_phone") or "").strip()
    name = str(arguments.get("name") or _full_name(arguments, {})).strip()
    date_value = _rpa_date(arguments.get("date") or slot.get("date") or slot.get("dateISO"))
    time_value = str(arguments.get("time") or slot.get("time") or "").strip()
    if not appointment_id or not phone or not date_value or not time_value:
        return None
    payload = {
        "idCita": appointment_id,
        "name": name or "Paciente",
        "phone": phone,
        "date": date_value,
        "time": time_value,
        "type": _rpa_service_type(str(arguments.get("service") or slot.get("service") or "")),
    }
    return payload


def _write_result(name: str, arguments: dict[str, Any], data: dict[str, Any]) -> ToolResult:
    if data.get("success") is not True:
        return _rpa_not_ok(name, data)
    slot = _selected_slot(arguments, slot_key="new_slot")
    normalized = {
        "ok": True,
        "success": True,
        "dry_run": False,
        "appointment_id": arguments.get("appointment_id") or arguments.get("idCita"),
        "date": slot.get("date"),
        "time": slot.get("time"),
        "start": _start_iso(slot.get("dateISO") or slot.get("date"), slot.get("time")),
        "message": data.get("message"),
    }
    return ToolResult(
        name=name,
        status="success",
        user_safe_summary="Operacion RPA completada.",
        data=redact_payload(normalized),
    )


def _selected_slot(
    arguments: dict[str, Any],
    *,
    slot_key: str = "selected_slot",
) -> dict[str, Any]:
    slot = arguments.get(slot_key)
    if isinstance(slot, dict):
        return dict(slot)
    slot_id = str(arguments.get("slot_id") or arguments.get("new_slot_id") or "")
    parsed = _slot_id_parts(slot_id)
    return parsed or {}


def _slot_id_parts(slot_id: str) -> dict[str, str] | None:
    if not slot_id or "T" not in slot_id:
        return None
    date_iso, time_value = slot_id.split("T", 1)
    if not re_match_date_iso(date_iso) or not re_match_time(time_value):
        return None
    return {
        "slot_id": slot_id,
        "date": _iso_to_ddmmyyyy(date_iso),
        "dateISO": date_iso,
        "time": time_value[:5],
    }


def _slot_from_real_response(
    *,
    slot_time: str,
    date: str,
    date_iso: str,
    clinic: str,
    service: str,
) -> dict[str, str]:
    time_value = slot_time[:5]
    start = _start_iso(date_iso, time_value)
    return {
        "slot_id": f"{date_iso}T{time_value}",
        "date": date,
        "dateISO": date_iso,
        "time": time_value,
        "start": start or f"{date_iso}T{time_value}:00+02:00",
        "clinic": clinic,
        "service": service,
        "address": clinic_address(clinic),
    }


def _normalize_appointment(
    item: dict[str, Any],
    arguments: dict[str, Any],
) -> dict[str, Any]:
    date_iso = str(item.get("date") or "")
    time_value = str(item.get("time") or "")
    appointment_id = item.get("idCita") or item.get("appointment_id")
    return {
        "appointment_id": str(appointment_id) if appointment_id is not None else None,
        "idCita": str(appointment_id) if appointment_id is not None else None,
        "date": date_iso,
        "dateReadable": item.get("dateReadable"),
        "time": time_value,
        "start": _start_iso(date_iso, time_value),
        "patient_name": item.get("nombre"),
        "patient_phone": item.get("telefono") or arguments.get("patient_phone"),
        "duration_minutes": item.get("duracionMin"),
        "observations": item.get("observaciones"),
        "clinic": arguments.get("clinic"),
        "address": clinic_address(str(arguments.get("clinic") or "")),
    }


def _full_name(arguments: dict[str, Any], patient: dict[str, Any]) -> str:
    if arguments.get("name"):
        return str(arguments["name"]).strip()
    first = str(patient.get("first_name") or arguments.get("patient_first_name") or "").strip()
    last = str(patient.get("last_names") or arguments.get("patient_last_names") or "").strip()
    return " ".join(part for part in [first, last] if part)


def _rpa_service_type(service: str) -> str:
    if service == "estudio_biomecanico":
        return "estudio"
    if service in {"podologia", "quiropodia"}:
        return "quiropodia"
    return service or "quiropodia"


def _mutua_id(provider: Any) -> int | None:
    if provider == "sanitas":
        return 1
    if provider == "catalana_occident":
        return 12
    return None


def _rpa_preference(value: Any) -> str:
    if value == "morning":
        return "mañana"
    if value == "afternoon":
        return "tarde"
    return "todos"


def _rpa_date(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    if re_match_date_es(value):
        return value
    if re_match_date_iso(value):
        return _iso_to_ddmmyyyy(value)
    today = datetime.now(ZoneInfo("Europe/Madrid")).date()
    if value == "relative_tomorrow":
        return (today + timedelta(days=1)).strftime("%d/%m/%Y")
    if value == "relative_day_after_tomorrow":
        return (today + timedelta(days=2)).strftime("%d/%m/%Y")
    if value.startswith("next_week:"):
        requested_weekday = weekday_index(value.split(":", 1)[1])
        if requested_weekday is not None:
            next_monday = today + timedelta(days=7 - today.weekday())
            return (next_monday + timedelta(days=requested_weekday)).strftime("%d/%m/%Y")
    if value.startswith("next:"):
        requested_weekday = weekday_index(value.split(":", 1)[1])
        if requested_weekday is not None:
            return _next_date_for_weekday(
                requested_weekday,
                include_today=False,
            ).strftime("%d/%m/%Y")
    requested_weekday = weekday_index(value)
    if requested_weekday is not None:
        next_date = _next_date_for_weekday(requested_weekday)
        return next_date.strftime("%d/%m/%Y")
    return None


def _requested_weekday(arguments: dict[str, Any]) -> int | None:
    for key in ("date", "date_preference"):
        value = arguments.get(key)
        if not isinstance(value, str) or not value:
            continue
        named_weekday = weekday_index(value)
        if named_weekday is None and ":" in value:
            named_weekday = weekday_index(value.split(":", 1)[1])
        if named_weekday is not None:
            return named_weekday
        date_iso = _date_to_iso(value)
        if date_iso:
            return datetime.fromisoformat(date_iso).weekday()
    return None


def _next_open_date(clinic: str, requested_weekday: int | None) -> datetime.date:
    if requested_weekday is not None:
        return _next_date_for_weekday(requested_weekday)
    today = datetime.now(ZoneInfo("Europe/Madrid")).date()
    for offset in range(7):
        candidate = today + timedelta(days=offset)
        if clinic_is_open_on_weekday(clinic, candidate.weekday()):
            return candidate
    raise ValueError(f"No open weekdays configured for {clinic}")


def _next_date_for_weekday(
    requested_weekday: int,
    *,
    include_today: bool = True,
) -> datetime.date:
    today = datetime.now(ZoneInfo("Europe/Madrid")).date()
    offset = (requested_weekday - today.weekday()) % 7
    if offset == 0 and not include_today:
        offset = 7
    return today + timedelta(days=offset)


def _slot_is_on_clinic_open_day(slot: dict[str, str], clinic: str) -> bool:
    date_iso = slot.get("dateISO") or _date_to_iso(slot.get("date", ""))
    if not date_iso:
        return True
    return clinic_is_open_on_weekday(clinic, datetime.fromisoformat(date_iso).weekday())


def _availability_without_slots(
    *,
    clinic: str,
    dry_run: bool,
    reason: str,
    requested_weekday: int | None,
) -> ToolResult:
    return ToolResult(
        name="rpa_search_availability",
        status="success",
        user_safe_summary="No hay disponibilidad compatible con el horario de la clinica.",
        data={
            "ok": True,
            "dry_run": dry_run,
            "slots": [],
            "clinic": clinic,
            "availability_reason": reason,
            "requested_weekday": weekday_name_es(requested_weekday),
        },
    )


def _date_to_iso(value: str) -> str | None:
    if re_match_date_iso(value):
        return value
    if not re_match_date_es(value):
        return None
    day, month, year = value.split("/")
    return f"{year}-{month}-{day}"


def _iso_to_ddmmyyyy(value: str) -> str:
    year, month, day = value.split("-")
    return f"{day}/{month}/{year}"


def _start_iso(date_value: Any, time_value: Any) -> str | None:
    if not isinstance(date_value, str) or not isinstance(time_value, str):
        return None
    date_iso = _date_to_iso(date_value) or date_value
    if not re_match_date_iso(date_iso) or not re_match_time(time_value):
        return None
    parsed = datetime.fromisoformat(f"{date_iso}T{time_value[:5]}:00")
    return parsed.replace(tzinfo=ZoneInfo("Europe/Madrid")).isoformat()


def _reminder(start: str | None) -> dict[str, Any] | None:
    if not start:
        return None
    try:
        parsed = datetime.fromisoformat(start)
    except ValueError:
        return None
    return {
        "send_at": (parsed - timedelta(hours=24)).isoformat(),
        "channel": "whatsapp",
        "template": "appointment_reminder_24h",
        "consent_prompt_required": False,
    }


def _rpa_http_error(name: str) -> ToolResult:
    return ToolResult(
        name=name,
        status="failed",
        user_safe_summary="La RPA no ha respondido correctamente.",
        internal_code="rpa_http_error",
    )


def _rpa_missing_fields(name: str) -> ToolResult:
    return ToolResult(
        name=name,
        status="failed",
        user_safe_summary="Faltan datos obligatorios para llamar a la RPA.",
        internal_code="rpa_missing_required_fields",
    )


def _rpa_not_ok(name: str, data: dict[str, Any]) -> ToolResult:
    return ToolResult(
        name=name,
        status="failed",
        user_safe_summary="La RPA no ha confirmado la operacion.",
        internal_code=str(data.get("error_code") or "rpa_not_ok"),
        data=redact_payload(data),
    )


def re_match_date_es(value: str) -> bool:
    import re

    return bool(re.fullmatch(r"\d{2}/\d{2}/\d{4}", value))


def re_match_date_iso(value: str) -> bool:
    import re

    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value))


def re_match_time(value: str) -> bool:
    import re

    return bool(re.fullmatch(r"\d{2}:\d{2}(?::\d{2})?", value))


def rpa_dry_run_from_env() -> bool:
    return os.environ.get("RPA_DRY_RUN", "true").lower() not in {"0", "false", "no"}
