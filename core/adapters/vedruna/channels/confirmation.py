from __future__ import annotations

import re

from core.adapters.vedruna.domain_schema import normalize_text


def is_explicit_confirmation(utterance: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", normalize_text(utterance)).strip()
    return normalized in {
        "si",
        "si confirmo",
        "confirmo",
        "confirmalo",
        "confirmar",
        "de acuerdo confirmo",
        "adelante confirmo",
    }
