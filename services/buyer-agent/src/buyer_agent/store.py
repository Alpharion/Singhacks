"""In-memory run store.

The buyer agent owns no database. SQLite belongs to the marketplace, and runs
are short-lived demo state, so a process-local dictionary with an idempotency
index is the right size. AgentRun is immutable, so every update replaces the
stored value rather than mutating it.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from .models import AgentRun


class IdempotencyConflict(Exception):
    """The same key arrived with a different request body."""


@dataclass
class RunStore:
    _runs: dict[str, AgentRun] = field(default_factory=dict)
    _by_key: dict[str, str] = field(default_factory=dict)
    _fingerprints: dict[str, str] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def claim(self, key: str, fingerprint: str) -> AgentRun | None:
        """Reserve an idempotency key, or return the run it already created."""
        async with self._lock:
            existing_run_id = self._by_key.get(key)
            if existing_run_id is None:
                self._fingerprints[key] = fingerprint
                return None
            if self._fingerprints.get(key) != fingerprint:
                raise IdempotencyConflict(key)
            return self._runs.get(existing_run_id)

    async def bind(self, key: str, run: AgentRun) -> None:
        async with self._lock:
            self._by_key[key] = run.run_id
            self._runs[run.run_id] = run

    async def get(self, run_id: str) -> AgentRun | None:
        async with self._lock:
            return self._runs.get(run_id)

    async def put(self, run: AgentRun) -> None:
        async with self._lock:
            self._runs[run.run_id] = run

    def put_now(self, run: AgentRun) -> None:
        """Synchronous publish for the agent's progress callback.

        The callback fires inside the run's own task, so a dict assignment is
        already serialized with respect to it; taking the async lock here would
        require an await the callback cannot make.
        """
        self._runs[run.run_id] = run

    async def all(self) -> list[AgentRun]:
        async with self._lock:
            return list(self._runs.values())
