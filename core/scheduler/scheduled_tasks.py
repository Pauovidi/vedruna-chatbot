from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

ScheduledStatus = Literal[
    "pending",
    "processing",
    "sent",
    "dry_run",
    "failed",
    "skipped",
]


class ScheduledTask(BaseModel):
    id: str = Field(default_factory=lambda: f"sched_{uuid4().hex}")
    task_type: str
    channel: str
    payload: dict[str, Any] = Field(default_factory=dict)
    scheduled_at: datetime
    dedupe_key: str
    status: ScheduledStatus = "pending"
    attempts: int = 0
    max_attempts: int = 3
    dry_run: bool = True
    safe_error_code: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ScheduledTaskResult(BaseModel):
    ok: bool = True
    processed: int = 0
    sent: int = 0
    dry_run: int = 0
    failed: int = 0
    skipped: int = 0


class MemoryScheduledTaskStore:
    def __init__(self) -> None:
        self._tasks: dict[str, ScheduledTask] = {}

    def upsert(self, task: ScheduledTask) -> ScheduledTask:
        existing = next(
            (item for item in self._tasks.values() if item.dedupe_key == task.dedupe_key),
            None,
        )
        if existing and existing.status in {"sent", "processing"}:
            return existing.model_copy(deep=True)
        next_task = task.model_copy(deep=True)
        if existing:
            next_task.id = existing.id
        self._tasks[next_task.id] = next_task
        return next_task.model_copy(deep=True)

    def list_due(self, now: datetime, limit: int = 50) -> list[ScheduledTask]:
        return [
            task.model_copy(deep=True)
            for task in sorted(self._tasks.values(), key=lambda item: item.scheduled_at)
            if task.status == "pending" and task.scheduled_at <= now
        ][:limit]

    def mark(self, task_id: str, status: ScheduledStatus, now: datetime) -> None:
        task = self._tasks[task_id]
        task.status = status
        task.updated_at = now
        task.attempts += 1

    def get_by_dedupe_key(self, dedupe_key: str) -> ScheduledTask | None:
        task = next(
            (item for item in self._tasks.values() if item.dedupe_key == dedupe_key),
            None,
        )
        return task.model_copy(deep=True) if task else None


class ScheduledTaskDispatcher:
    def __init__(self, store: MemoryScheduledTaskStore) -> None:
        self.store = store

    def dispatch_due(self, *, now: datetime, dry_run: bool = True) -> ScheduledTaskResult:
        result = ScheduledTaskResult()
        for task in self.store.list_due(now):
            result.processed += 1
            if task.dry_run or dry_run:
                self.store.mark(task.id, "dry_run", now)
                result.dry_run += 1
                continue
            self.store.mark(task.id, "sent", now)
            result.sent += 1
        return result
