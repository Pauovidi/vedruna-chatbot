from __future__ import annotations

import re

from core.adapters.vedruna.domain_schema import normalize_text


def is_explicit_confirmation(utterance: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", normalize_text(utterance)).strip()
    if normalized in {
        "si",
        "si confirmo",
        "confirmo",
        "confirmalo",
        "confirmar",
        "de acuerdo confirmo",
        "adelante confirmo",
    }:
        return True
    return bool(
        re.fullmatch(
            r"(?:si )?(?:confirmo|confirmar|confirmalo)"
            r"(?: (?:la|esta|esa|mi))?"
            r"(?: (?:cita|cancelacion|modificacion|reprogramacion))?"
            r"(?: que quiero (?:cancelarla|modificarla|reprogramarla))?",
            normalized,
        )
    )
