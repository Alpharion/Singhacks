from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from collections.abc import Sequence

from x402_xrpl.types import PaymentRequirements


class SQLiteInvoiceStore:
    """Persistent provider invoice store implementing x402-xrpl's protocol."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS x402_invoices (
                    invoice_id TEXT PRIMARY KEY,
                    requirements_json TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    consumed INTEGER NOT NULL DEFAULT 0
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=5)

    async def put(
        self,
        invoice_id: str,
        reqs: Sequence[PaymentRequirements],
        *,
        ttl_seconds: int,
    ) -> None:
        payload = json.dumps(
            [requirement.to_dict() for requirement in reqs],
            separators=(",", ":"),
            sort_keys=True,
        )
        now = time.time()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT requirements_json, expires_at, consumed
                FROM x402_invoices WHERE invoice_id = ?
                """,
                (invoice_id,),
            ).fetchone()
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO x402_invoices (
                        invoice_id, requirements_json, expires_at, consumed
                    ) VALUES (?, ?, ?, 0)
                    """,
                    (invoice_id, payload, now + ttl_seconds),
                )
                return
            if existing[0] != payload:
                raise ValueError(
                    "invoice id was reused with different payment requirements"
                )
            if existing[2]:
                raise ValueError("invoice has already been consumed")
            if existing[1] <= now:
                connection.execute(
                    """
                    UPDATE x402_invoices SET expires_at = ?, consumed = 0
                    WHERE invoice_id = ?
                    """,
                    (now + ttl_seconds, invoice_id),
                )

    async def get(
        self,
        invoice_id: str,
    ) -> Sequence[PaymentRequirements] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT requirements_json, expires_at, consumed
                FROM x402_invoices WHERE invoice_id = ?
                """,
                (invoice_id,),
            ).fetchone()
        if row is None or row[2] or row[1] <= time.time():
            return None
        raw_requirements = json.loads(row[0])
        return [
            PaymentRequirements.from_dict(requirement)
            for requirement in raw_requirements
        ]

    async def consume(self, invoice_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE x402_invoices SET consumed = 1 WHERE invoice_id = ?",
                (invoice_id,),
            )

    def delete_expired(self) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM x402_invoices WHERE expires_at <= ?",
                (time.time(),),
            )
            return cursor.rowcount
