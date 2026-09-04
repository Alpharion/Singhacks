"""Identifier construction.

Contract identifiers match ``^[a-z][a-z0-9_-]{2,63}$``. Invoice and idempotency
keys are looser strings but must satisfy the ``Idempotency-Key`` header pattern
``^[A-Za-z0-9._:-]{8,128}$``.
"""

from __future__ import annotations

import re
import uuid

_ILLEGAL = re.compile(r"[^a-z0-9_-]+")


def identifier(prefix: str, *parts: str) -> str:
    """Build a contract-valid identifier, truncated to the 64-character limit."""
    raw = "_".join([prefix, *parts]).lower()
    cleaned = _ILLEGAL.sub("_", raw).strip("_-")
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"{prefix}_{cleaned}".strip("_-")
    return cleaned[:64]


def unique(prefix: str) -> str:
    return identifier(prefix, uuid.uuid4().hex[:12])


def invoice_id(run_id: str, resource_id: str, version: int = 1) -> str:
    """Opaque reference bound to one run and one resource.

    This is the only order-related value that reaches the ledger, and it carries
    no buyer, dietary, or address detail.
    """
    return f"inv:{run_id}:{resource_id}:v{version}"


def idempotency_key(run_id: str, resource_id: str, version: int = 1) -> str:
    return f"idem:{run_id}:{resource_id}:v{version}"
