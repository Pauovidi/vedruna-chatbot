from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field

ClientIdentityStatus = Literal["known", "unknown", "ambiguous", "blocked"]


class ClientDirectoryEntry(BaseModel):
    external_id: str
    lookup_key: str
    display_name: str | None = None
    blocked: bool = False
    metadata: dict[str, str] = Field(default_factory=dict)


class ClientIdentityResolution(BaseModel):
    status: ClientIdentityStatus
    external_id: str | None = None
    display_name_safe: str | None = None
    match_count: int = 0
    cache_hit: bool = False
    safe_reason: str


class _CacheEntry(BaseModel):
    resolution: ClientIdentityResolution
    expires_at: datetime


class MemoryClientDirectory:
    def __init__(
        self,
        entries: list[ClientDirectoryEntry] | None = None,
        *,
        ttl_seconds: int = 300,
    ) -> None:
        self.entries = entries or []
        self.ttl = timedelta(seconds=ttl_seconds)
        self._cache: dict[str, _CacheEntry] = {}

    def resolve(
        self,
        lookup_key: str,
        *,
        now: datetime | None = None,
    ) -> ClientIdentityResolution:
        now = now or datetime.utcnow()
        cached = self._cache.get(lookup_key)
        if cached and cached.expires_at > now:
            return cached.resolution.model_copy(update={"cache_hit": True})

        matches = [entry for entry in self.entries if entry.lookup_key == lookup_key]
        resolution = self._resolve_matches(matches)
        self._cache[lookup_key] = _CacheEntry(
            resolution=resolution,
            expires_at=now + self.ttl,
        )
        return resolution

    def _resolve_matches(
        self,
        matches: list[ClientDirectoryEntry],
    ) -> ClientIdentityResolution:
        if not matches:
            return ClientIdentityResolution(
                status="unknown",
                match_count=0,
                safe_reason="no_directory_match",
            )
        if any(match.blocked for match in matches):
            return ClientIdentityResolution(
                status="blocked",
                match_count=len(matches),
                safe_reason="blocked_directory_match",
            )
        if len(matches) > 1:
            return ClientIdentityResolution(
                status="ambiguous",
                match_count=len(matches),
                safe_reason="multiple_directory_matches",
            )
        entry = matches[0]
        return ClientIdentityResolution(
            status="known",
            external_id=entry.external_id,
            display_name_safe=_safe_display_name(entry.display_name),
            match_count=1,
            safe_reason="single_directory_match",
        )


def _safe_display_name(value: str | None) -> str | None:
    if not value:
        return None
    return " ".join(value.split())[:80]
