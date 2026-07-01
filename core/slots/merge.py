from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SlotMergeInput(BaseModel):
    current_slots: dict[str, Any] = Field(default_factory=dict)
    incoming_slots: dict[str, Any] = Field(default_factory=dict)
    target_slots: dict[str, Any] = Field(default_factory=dict)
    pending_fields: list[str] = Field(default_factory=list)
    corrections: list[str] = Field(default_factory=list)
    allow_out_of_order: bool = True


class SlotMergeResult(BaseModel):
    slots: dict[str, Any]
    applied: list[str] = Field(default_factory=list)
    ignored: list[str] = Field(default_factory=list)
    ignored_reasons: dict[str, str] = Field(default_factory=dict)
    pending_fields: list[str] = Field(default_factory=list)


def merge_slots(input_data: SlotMergeInput) -> SlotMergeResult:
    slots = dict(input_data.current_slots)
    applied: list[str] = []
    ignored: list[str] = []
    ignored_reasons: dict[str, str] = {}
    allowed = set(input_data.pending_fields)
    allowed.update(input_data.corrections)

    for name, value in input_data.incoming_slots.items():
        target_name = _resolve_target_name(name, value, input_data)
        value = _resolve_same_value(target_name, value, input_data.current_slots)
        if value in (None, ""):
            ignored.append(name)
            ignored_reasons[name] = "empty_value"
            continue
        if allowed and not input_data.allow_out_of_order and target_name not in allowed:
            ignored.append(name)
            ignored_reasons[name] = "not_currently_pending"
            continue
        if slots.get(target_name) != value:
            slots[target_name] = value
            applied.append(target_name)

    pending = [
        field
        for field in input_data.pending_fields
        if slots.get(field) in (None, "")
    ]
    return SlotMergeResult(
        slots=slots,
        applied=applied,
        ignored=ignored,
        ignored_reasons=ignored_reasons,
        pending_fields=pending,
    )


def _resolve_target_name(name: str, value: Any, input_data: SlotMergeInput) -> str:
    target = input_data.target_slots.get(name)
    mode = target
    explicit_slot = None
    if isinstance(target, dict):
        mode = target.get("mode")
        explicit_slot = target.get("slot")
    if isinstance(explicit_slot, str) and explicit_slot:
        return explicit_slot
    if mode in {"currentPending", "current_pending"}:
        pending = _first_pending_same_family(name, input_data.pending_fields)
        if pending:
            return pending
    if mode in {"entry", "exit", "both"} and isinstance(value, dict):
        candidate = value.get(mode) or value.get("value")
        if isinstance(candidate, str):
            return f"{name}_{mode}"
    return name


def _resolve_same_value(name: str, value: Any, current_slots: dict[str, Any]) -> Any:
    if not isinstance(value, str):
        return value
    normalized = value.lower().strip()
    if normalized not in {"same_time", "misma_hora", "same hour", "tambien"}:
        return value
    if _slot_family(name) != "time":
        return value
    for current_name, current_value in current_slots.items():
        if _slot_family(current_name) == "time" and current_value not in (None, ""):
            return current_value
    return value


def _first_pending_same_family(name: str, pending_fields: list[str]) -> str | None:
    family = _slot_family(name)
    for field in pending_fields:
        if _slot_family(field) == family:
            return field
    return pending_fields[0] if pending_fields else None


def _slot_family(name: str) -> str:
    lowered = name.lower()
    if "time" in lowered or "hora" in lowered:
        return "time"
    if "date" in lowered or "fecha" in lowered or "day" in lowered:
        return "date"
    if "phone" in lowered or "telefono" in lowered:
        return "phone"
    if "name" in lowered or "nombre" in lowered:
        return "name"
    return lowered
