"""Idempotency-Key handling shared by seller and courier routers.

Contract Freeze v1.0.0: "An `Idempotency-Key` header is required for every
state-changing request... Provider payment retries reuse the same request
body and idempotency key... The `Idempotency-Key` header must equal
`PurchaseIntent.idempotencyKey`." This module stores the first response for
a key and replays it verbatim on retry, and rejects key reuse against a
different request body.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from .errors import ApiException, new_request_id
from .models import IdempotencyRecordRow
from .time_utils import now_utc


def _fingerprint(body: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _record_key(scope: str, idempotency_key: str) -> str:
    return f"{scope}:{idempotency_key}"


class ReplayedResponse(Exception):
    """Raised to short-circuit a route back to a previously stored response."""

    def __init__(self, status_code: int, body: dict[str, Any], headers: dict[str, str]) -> None:
        super().__init__("idempotent replay")
        self.status_code = status_code
        self.body = body
        self.headers = headers


def check_idempotency(
    session: Session, *, scope: str, idempotency_key: str, request_body: dict[str, Any]
) -> None:
    """Raise `ReplayedResponse` on a stored match, or `ApiException` on a key/body conflict."""

    existing = session.get(IdempotencyRecordRow, _record_key(scope, idempotency_key))
    if existing is None:
        return
    if existing.request_fingerprint != _fingerprint(request_body):
        raise ApiException(
            error="invalid_request",
            message="Idempotency-Key was already used for a different request body.",
            status_code=409,
            retryable=False,
        )
    raise ReplayedResponse(existing.response_status, existing.response_body, existing.response_headers)


def store_idempotent_response(
    session: Session,
    *,
    scope: str,
    idempotency_key: str,
    request_body: dict[str, Any],
    status_code: int,
    response_body: dict[str, Any],
    headers: dict[str, str] | None = None,
) -> None:
    row = IdempotencyRecordRow(
        record_key=_record_key(scope, idempotency_key),
        request_fingerprint=_fingerprint(request_body),
        response_status=status_code,
        response_body=response_body,
        response_headers=headers or {},
        created_at=now_utc(),
    )
    session.add(row)
    session.commit()


__all__ = [
    "ReplayedResponse",
    "check_idempotency",
    "store_idempotent_response",
    "new_request_id",
]
