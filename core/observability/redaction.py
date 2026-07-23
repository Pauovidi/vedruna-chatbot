from __future__ import annotations

import re
from typing import Any

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)")
SECRET_KEYS = {"api_key", "token", "secret", "password", "authorization"}
TEMPORAL_KEYS = {"start", "end", "date", "dateISO", "time"}


def redact_text(value: str) -> str:
    value = EMAIL_RE.sub("[redacted_email]", value)
    return PHONE_RE.sub("[redacted_phone]", value)


def redact_payload(payload: Any) -> Any:
    if isinstance(payload, str):
        return redact_text(payload)
    if isinstance(payload, list):
        return [redact_payload(item) for item in payload]
    if isinstance(payload, dict):
        clean = {}
        for key, value in payload.items():
            if key.lower() in SECRET_KEYS:
                clean[key] = "[redacted]"
            elif key in TEMPORAL_KEYS and isinstance(value, str):
                clean[key] = value
            else:
                clean[key] = redact_payload(value)
        return clean
    return payload
