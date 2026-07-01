from __future__ import annotations

import re
import unicodedata
from enum import StrEnum
from typing import Any

VEDRUNA_CLIENT_ID = "vedruna"


class Clinic(StrEnum):
    MADRE_VEDRUNA = "madre_vedruna"
    SANTA_ISABEL = "santa_isabel"
    UNKNOWN = "unknown"


class Service(StrEnum):
    PODOLOGIA = "podologia"
    QUIROPODIA = "quiropodia"
    ESTUDIO_BIOMECANICO = "estudio_biomecanico"
    INFILTRACION = "infiltracion"
    ECOGRAFIA = "ecografia"
    OTRO_PROBLEMA = "otro_problema"
    TRAUMATOLOGIA = "traumatologia"
    PSICOLOGIA = "psicologia"
    UNKNOWN = "unknown"


class InsuranceProvider(StrEnum):
    SANITAS = "sanitas"
    GENERALI = "generali"
    OTHER = "other"
    NONE = "none"
    UNKNOWN = "unknown"


CLINICS: dict[str, dict[str, Any]] = {
    Clinic.MADRE_VEDRUNA.value: {
        "label": "Clinica Madre Vedruna",
        "address": "Madre Vedruna 14, bajo derecha",
        "phone": "976795117",
        "hours": (
            "martes y jueves de 09:30 a 13:30 y de 15:30 a 19:30, "
            "y viernes de 09:00 a 17:00"
        ),
        "allowed_services": {Service.PODOLOGIA.value},
        "requires_insurance": True,
    },
    Clinic.SANTA_ISABEL.value: {
        "label": "Clinica Santa Isabel",
        "address": "Avenida Santa Isabel numero 82, local, 50016 Zaragoza",
        "phone": "976582768",
        "hours": "lunes y miercoles de 09:30 a 13:30 y de 15:30 a 19:30",
        "allowed_services": {
            Service.QUIROPODIA.value,
            Service.ESTUDIO_BIOMECANICO.value,
            Service.INFILTRACION.value,
            Service.ECOGRAFIA.value,
            Service.OTRO_PROBLEMA.value,
        },
        "requires_insurance": False,
    },
}

REQUIRED_BOOKING_FIELDS = [
    "clinic",
    "service",
    "patient_first_name",
    "patient_last_names",
    "patient_phone",
    "consultation_reason",
    "date_preference",
]

WEEKDAY_MAP = {
    "lunes": "monday",
    "martes": "tuesday",
    "miercoles": "wednesday",
    "jueves": "thursday",
    "viernes": "friday",
}


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", value.lower())
    return "".join(char for char in text if not unicodedata.combining(char)).strip()


def normalize_clinic(text: str) -> str | None:
    normalized = normalize_text(text)
    if "santa isabel" in normalized or "avenida santa isabel" in normalized:
        return Clinic.SANTA_ISABEL.value
    if "vedruna" in normalized or "madre vedruna" in normalized:
        return Clinic.MADRE_VEDRUNA.value
    return None


def normalize_service(text: str, clinic: str | None = None) -> str | None:
    normalized = normalize_text(text)
    if "traumatolog" in normalized:
        return Service.TRAUMATOLOGIA.value
    if "psicolog" in normalized:
        return Service.PSICOLOGIA.value
    if any(term in normalized for term in ["biomecan", "pisada", "marcha"]):
        return Service.ESTUDIO_BIOMECANICO.value
    if "infiltr" in normalized:
        return Service.INFILTRACION.value
    if "ecograf" in normalized:
        return Service.ECOGRAFIA.value
    if any(term in normalized for term in ["quiropodia", "unas", "durezas", "callos"]):
        return Service.QUIROPODIA.value
    if "podolog" in normalized:
        if clinic == Clinic.SANTA_ISABEL.value:
            return Service.QUIROPODIA.value
        return Service.PODOLOGIA.value
    if any(term in normalized for term in ["dolor", "molestia", "problema"]):
        return Service.OTRO_PROBLEMA.value
    return None


def normalize_insurance(text: str) -> dict[str, str] | None:
    normalized = normalize_text(text)
    if "sanitas" in normalized:
        return {
            "insurance_type": "seguro",
            "insurance_provider": InsuranceProvider.SANITAS.value,
        }
    if "generali" in normalized:
        return {
            "insurance_type": "seguro",
            "insurance_provider": InsuranceProvider.GENERALI.value,
        }
    if any(term in normalized for term in ["particular", "sin seguro"]):
        return {
            "insurance_type": "particular",
            "insurance_provider": InsuranceProvider.NONE.value,
        }
    if "seguro" in normalized:
        return {
            "insurance_type": "seguro",
            "insurance_provider": InsuranceProvider.UNKNOWN.value,
        }
    return None


def normalize_date_preference(text: str) -> str | None:
    normalized = normalize_text(text)
    for spanish, canonical in WEEKDAY_MAP.items():
        if spanish in normalized:
            return canonical
    if "pasado manana" in normalized:
        return "relative_day_after_tomorrow"
    if "manana" in normalized:
        return "relative_tomorrow"
    return None


def normalize_time_preference(text: str) -> str | None:
    normalized = normalize_text(text)
    if "manana" in normalized:
        return "morning"
    if "tarde" in normalized:
        return "afternoon"
    match = re.search(r"\b(?:a las|sobre las)?\s*(\d{1,2})(?::(\d{2}))?\b", normalized)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def appointment_duration_minutes(service: str | None) -> int:
    return 30 if service == Service.ESTUDIO_BIOMECANICO.value else 20


def clinic_label(clinic: str | None) -> str:
    return CLINICS.get(clinic or "", {}).get("label", "la clinica")


def clinic_phone(clinic: str | None) -> str:
    return CLINICS.get(clinic or "", {}).get("phone", "")


def clinic_address(clinic: str | None) -> str:
    return CLINICS.get(clinic or "", {}).get("address", "")


def service_allowed(clinic: str | None, service: str | None) -> bool:
    if not clinic or not service:
        return False
    return service in CLINICS.get(clinic, {}).get("allowed_services", set())


def unsupported_service(service: str | None) -> bool:
    return service in {Service.TRAUMATOLOGIA.value, Service.PSICOLOGIA.value}


def requires_insurance(clinic: str | None) -> bool:
    return bool(CLINICS.get(clinic or "", {}).get("requires_insurance", False))


def missing_booking_fields(slots: dict[str, Any]) -> list[str]:
    missing = [field for field in REQUIRED_BOOKING_FIELDS if not slots.get(field)]
    clinic = slots.get("clinic")
    if requires_insurance(clinic) and not slots.get("insurance_type"):
        missing.insert(2, "insurance_type")
    return missing


def ready_for_availability(slots: dict[str, Any]) -> bool:
    return not missing_booking_fields(slots)


def ready_for_create(slots: dict[str, Any]) -> bool:
    return ready_for_availability(slots) and bool(slots.get("selected_slot_id"))
