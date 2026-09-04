from __future__ import annotations

from datetime import UTC, datetime


def now_utc() -> datetime:
    return datetime.now(UTC)


def ensure_aware(value: datetime) -> datetime:
    """SQLite drops tzinfo on round-trip; treat naive values read back as UTC."""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def to_iso(value: datetime) -> str:
    return ensure_aware(value).astimezone(UTC).isoformat().replace("+00:00", "Z")
