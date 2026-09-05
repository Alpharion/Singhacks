from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
import uuid
from collections.abc import Mapping, Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_INVOICE_ID = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_request_invoice_id: ContextVar[str | None] = ContextVar(
    "surplusflow_request_invoice_id",
    default=None,
)
@dataclass(frozen=True)
class ProviderRequestContext:
    """Validated request metadata available to provider payment callbacks."""

    method: str
    path: str
    payload: Mapping[str, object]
    invoice_id: str
    idempotency_key: str
    fingerprint: str


_provider_request_context: ContextVar[ProviderRequestContext | None] = ContextVar(
    "surplusflow_provider_request_context",
    default=None,
)


def current_request_invoice_id() -> str:
    invoice_id = _request_invoice_id.get()
    if invoice_id is None:
        raise RuntimeError(
            "provider invoice context is unavailable; install the complete "
            "SurplusFlow provider payment stack"
        )
    return invoice_id


def current_provider_request() -> ProviderRequestContext:
    context = _provider_request_context.get()
    if context is None:
        raise RuntimeError(
            "provider request context is unavailable; install the complete "
            "SurplusFlow provider payment stack"
        )
    return context


class ClaimStatus(StrEnum):
    NEW = "new"
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class CachedProviderResponse:
    status_code: int
    headers: tuple[tuple[bytes, bytes], ...]
    body: bytes


@dataclass(frozen=True)
class IdempotencyClaim:
    status: ClaimStatus
    response: CachedProviderResponse | None = None


class SQLiteProviderResponseStore:
    """Durably replay paid provider responses without re-settling an invoice."""

    def __init__(
        self,
        path: str | Path,
        *,
        pending_ttl_seconds: int = 900,
    ) -> None:
        self.path = Path(path)
        self.pending_ttl_seconds = pending_ttl_seconds
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS provider_responses (
                    idempotency_key TEXT PRIMARY KEY,
                    request_fingerprint TEXT NOT NULL,
                    state TEXT NOT NULL,
                    status_code INTEGER,
                    headers_json TEXT,
                    body BLOB,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def claim(self, idempotency_key: str, fingerprint: str) -> IdempotencyClaim:
        now = time.time()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT * FROM provider_responses
                WHERE idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO provider_responses (
                        idempotency_key, request_fingerprint, state,
                        created_at, updated_at
                    ) VALUES (?, ?, 'pending', ?, ?)
                    """,
                    (idempotency_key, fingerprint, now, now),
                )
                return IdempotencyClaim(ClaimStatus.NEW)

            if row["request_fingerprint"] != fingerprint:
                return IdempotencyClaim(ClaimStatus.CONFLICT)

            if row["state"] == "completed":
                return IdempotencyClaim(
                    ClaimStatus.COMPLETED,
                    CachedProviderResponse(
                        status_code=int(row["status_code"]),
                        headers=tuple(
                            (name.encode("latin-1"), value.encode("latin-1"))
                            for name, value in json.loads(row["headers_json"])
                        ),
                        body=bytes(row["body"]),
                    ),
                )

            if row["updated_at"] > now - self.pending_ttl_seconds:
                return IdempotencyClaim(ClaimStatus.IN_PROGRESS)

            connection.execute(
                """
                UPDATE provider_responses
                SET state = 'pending', updated_at = ?
                WHERE idempotency_key = ?
                """,
                (now, idempotency_key),
            )
            return IdempotencyClaim(ClaimStatus.NEW)

    def complete(
        self,
        idempotency_key: str,
        fingerprint: str,
        *,
        status_code: int,
        headers: Sequence[tuple[bytes, bytes]],
        body: bytes,
    ) -> None:
        headers_json = json.dumps(
            [
                [name.decode("latin-1"), value.decode("latin-1")]
                for name, value in headers
            ],
            separators=(",", ":"),
        )
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE provider_responses
                SET state = 'completed', status_code = ?, headers_json = ?,
                    body = ?, updated_at = ?
                WHERE idempotency_key = ? AND request_fingerprint = ?
                    AND state = 'pending'
                """,
                (
                    status_code,
                    headers_json,
                    body,
                    time.time(),
                    idempotency_key,
                    fingerprint,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError("idempotency claim is not pending")

    def release(self, idempotency_key: str, fingerprint: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM provider_responses
                WHERE idempotency_key = ? AND request_fingerprint = ?
                    AND state = 'pending'
                """,
                (idempotency_key, fingerprint),
            )


def request_fingerprint(scope: Scope, body: bytes) -> str:
    try:
        canonical_body = json.dumps(
            json.loads(body),
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    except (TypeError, ValueError, json.JSONDecodeError):
        canonical_body = body
    digest = hashlib.sha256()
    digest.update(str(scope.get("method", "")).upper().encode())
    digest.update(b"\x00")
    digest.update(str(scope.get("path", "")).encode())
    digest.update(b"\x00")
    digest.update(bytes(scope.get("query_string", b"")))
    digest.update(b"\x00")
    digest.update(canonical_body)
    return digest.hexdigest()


class ProviderIdempotencyMiddleware:
    """Cache the paid response outside x402 so retries never pay twice."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        store: SQLiteProviderResponseStore,
        protected_paths: str | Sequence[str],
    ) -> None:
        self.app = app
        self.store = store
        self.protected_paths = (
            {protected_paths}
            if isinstance(protected_paths, str)
            else set(protected_paths)
        )

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if (
            scope["type"] != "http"
            or scope.get("method") == "OPTIONS"
            or scope.get("path") not in self.protected_paths
        ):
            await self.app(scope, receive, send)
            return

        headers = {
            name.decode("latin-1").lower(): value.decode("latin-1")
            for name, value in scope.get("headers", [])
        }
        idempotency_key = headers.get("idempotency-key", "")
        if not _IDEMPOTENCY_KEY.fullmatch(idempotency_key):
            await self._error(
                scope,
                receive,
                send,
                status_code=422,
                error="invalid_request",
                message=(
                    "Idempotency-Key is required and must match the frozen "
                    "identifier format"
                ),
                retryable=False,
            )
            return

        request_messages: list[Message] = []
        body_parts: list[bytes] = []
        more_body = True
        while more_body:
            message = await receive()
            request_messages.append(message)
            if message["type"] == "http.request":
                body_parts.append(message.get("body", b""))
                more_body = bool(message.get("more_body", False))
            else:
                more_body = False
        body = b"".join(body_parts)
        try:
            payload = json.loads(body)
            invoice_id = payload["invoiceId"]
            body_idempotency_key = payload["idempotencyKey"]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            await self._error(
                scope,
                self._replay_receive(request_messages),
                send,
                status_code=422,
                error="invalid_request",
                message=(
                    "Protected provider requests require invoiceId and "
                    "idempotencyKey in a JSON body"
                ),
                retryable=False,
            )
            return
        if not isinstance(invoice_id, str) or not _INVOICE_ID.fullmatch(
            invoice_id
        ):
            await self._error(
                scope,
                self._replay_receive(request_messages),
                send,
                status_code=422,
                error="invalid_request",
                message="invoiceId does not match the frozen identifier format",
                retryable=False,
            )
            return
        if body_idempotency_key != idempotency_key:
            await self._error(
                scope,
                self._replay_receive(request_messages),
                send,
                status_code=422,
                error="invalid_request",
                message=(
                    "Idempotency-Key must equal the request body idempotencyKey"
                ),
                retryable=False,
            )
            return

        fingerprint = request_fingerprint(scope, body)
        claim = self.store.claim(idempotency_key, fingerprint)

        if claim.status is ClaimStatus.CONFLICT:
            await self._error(
                scope,
                self._replay_receive(request_messages),
                send,
                status_code=409,
                error="payment_replayed",
                message="Idempotency-Key was reused for a different request",
                retryable=False,
                request_id=idempotency_key,
            )
            return
        if claim.status is ClaimStatus.IN_PROGRESS:
            await self._error(
                scope,
                self._replay_receive(request_messages),
                send,
                status_code=409,
                error="payment_replayed",
                message="An identical provider request is already in progress",
                retryable=True,
                request_id=idempotency_key,
            )
            return
        if claim.status is ClaimStatus.COMPLETED:
            assert claim.response is not None
            await send(
                {
                    "type": "http.response.start",
                    "status": claim.response.status_code,
                    "headers": list(claim.response.headers),
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": claim.response.body,
                    "more_body": False,
                }
            )
            return

        response_messages: list[Message] = []

        async def capture(message: Message) -> None:
            response_messages.append(message)

        context = ProviderRequestContext(
            method=str(scope.get("method", "")).upper(),
            path=str(scope.get("path", "")),
            payload=MappingProxyType(dict(payload)),
            invoice_id=invoice_id,
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
        )
        invoice_token = _request_invoice_id.set(invoice_id)
        context_token = _provider_request_context.set(context)
        try:
            await self.app(
                scope,
                self._replay_receive(request_messages),
                capture,
            )
        except Exception:
            self.store.release(idempotency_key, fingerprint)
            raise
        finally:
            _provider_request_context.reset(context_token)
            _request_invoice_id.reset(invoice_token)

        start = next(
            message
            for message in response_messages
            if message["type"] == "http.response.start"
        )
        response_headers = list(start.get("headers", []))
        response_body = b"".join(
            message.get("body", b"")
            for message in response_messages
            if message["type"] == "http.response.body"
        )
        has_payment_response = any(
            name.lower() == b"payment-response"
            for name, _value in response_headers
        )
        if has_payment_response:
            self.store.complete(
                idempotency_key,
                fingerprint,
                status_code=int(start["status"]),
                headers=response_headers,
                body=response_body,
            )
        else:
            self.store.release(idempotency_key, fingerprint)

        for message in response_messages:
            await send(message)

    @staticmethod
    def _replay_receive(messages: Sequence[Message]) -> Receive:
        queued = list(messages)

        async def replay() -> Message:
            if queued:
                return queued.pop(0)
            return {"type": "http.request", "body": b"", "more_body": False}

        return replay

    @staticmethod
    async def _error(
        scope: Scope,
        receive: Receive,
        send: Send,
        *,
        status_code: int,
        error: str,
        message: str,
        retryable: bool,
        request_id: str | None = None,
    ) -> None:
        response = JSONResponse(
            status_code=status_code,
            content={
                "error": error,
                "message": message,
                "retryable": retryable,
                "requestId": request_id or f"request_{uuid.uuid4().hex}",
            },
        )
        await response(scope, receive, send)
