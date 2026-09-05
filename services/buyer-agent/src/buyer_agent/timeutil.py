"""ISO-8601 helpers.

The contract stores timestamps as strings. Every timestamp this service emits
is UTC with a trailing ``Z`` so fixtures and live payloads look identical.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc


def local_zone() -> ZoneInfo:
    """Timezone used to read wall-clock phrases such as "by 6 PM"."""
    return ZoneInfo(os.getenv("SURPLUSFLOW_TIMEZONE", "Asia/Singapore"))


def now() -> datetime:
    return datetime.now(UTC)


def iso(moment: datetime) -> str:
    """Render a datetime as the contract's UTC ``...Z`` form."""
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(value: str) -> datetime:
    """Parse a contract timestamp into an aware UTC datetime."""
    moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC)


def hours_between(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() / 3600.0


def minutes_between(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() / 60.0


def plus(moment: datetime, **kwargs: float) -> datetime:
    return moment + timedelta(**kwargs)
