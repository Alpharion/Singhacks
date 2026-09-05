from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .errors import DuplicatePaymentError, PaymentInProgressError
from .models import JournalStatus, PaymentJournalEntry, PurchaseIntent


def _now() -> str:
    return datetime.now(UTC).isoformat()


class PaymentJournal:
    """Persistent payment state that never stores seeds or signed blobs."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS payment_attempts (
                    invoice_id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    payee TEXT NOT NULL,
                    amount_drops TEXT NOT NULL,
                    transaction_hash TEXT,
                    error_code TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def begin(self, intent: PurchaseIntent) -> None:
        timestamp = _now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM payment_attempts WHERE invoice_id = ? OR idempotency_key = ?",
                (intent.invoice_id, intent.idempotency_key),
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO payment_attempts (
                        invoice_id, idempotency_key, status, payee, amount_drops,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        intent.invoice_id,
                        intent.idempotency_key,
                        JournalStatus.PENDING.value,
                        intent.pay_to,
                        intent.amount_drops,
                        timestamp,
                        timestamp,
                    ),
                )
                return

            if (
                row["invoice_id"] != intent.invoice_id
                or row["idempotency_key"] != intent.idempotency_key
                or row["payee"] != intent.pay_to
                or row["amount_drops"] != intent.amount_drops
            ):
                raise DuplicatePaymentError(
                    "invoice or idempotency key was reused with different payment terms"
                )

            status = JournalStatus(row["status"])
            if status is JournalStatus.VALIDATED:
                raise DuplicatePaymentError("invoice has already been paid")
            if status in {
                JournalStatus.PENDING,
                JournalStatus.SIGNED,
                JournalStatus.UNCERTAIN,
            }:
                raise PaymentInProgressError(
                    "payment is pending reconciliation and must not be resubmitted"
                )

            connection.execute(
                """
                UPDATE payment_attempts
                SET status = ?, transaction_hash = NULL, error_code = NULL, updated_at = ?
                WHERE invoice_id = ?
                """,
                (JournalStatus.PENDING.value, timestamp, intent.invoice_id),
            )

    def record_signed(self, invoice_id: str, transaction_hash: str) -> None:
        self._transition(
            invoice_id,
            JournalStatus.SIGNED,
            transaction_hash=transaction_hash.upper(),
        )

    def record_validated(self, invoice_id: str, transaction_hash: str) -> None:
        self._transition(
            invoice_id,
            JournalStatus.VALIDATED,
            transaction_hash=transaction_hash.upper(),
        )

    def record_failed(self, invoice_id: str, error_code: str) -> None:
        self._transition(
            invoice_id,
            JournalStatus.FAILED,
            error_code=error_code,
        )

    def record_uncertain(
        self,
        invoice_id: str,
        transaction_hash: str,
        error_code: str,
    ) -> None:
        self._transition(
            invoice_id,
            JournalStatus.UNCERTAIN,
            transaction_hash=transaction_hash.upper(),
            error_code=error_code,
        )

    def _transition(
        self,
        invoice_id: str,
        status: JournalStatus,
        *,
        transaction_hash: str | None = None,
        error_code: str | None = None,
    ) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE payment_attempts
                SET status = ?,
                    transaction_hash = COALESCE(?, transaction_hash),
                    error_code = ?,
                    updated_at = ?
                WHERE invoice_id = ?
                """,
                (
                    status.value,
                    transaction_hash,
                    error_code,
                    _now(),
                    invoice_id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"unknown invoice: {invoice_id}")

    def get(self, invoice_id: str) -> PaymentJournalEntry | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM payment_attempts WHERE invoice_id = ?",
                (invoice_id,),
            ).fetchone()
        if row is None:
            return None
        return PaymentJournalEntry.model_validate(dict(row))
