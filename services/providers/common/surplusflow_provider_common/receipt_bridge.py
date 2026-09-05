"""Bridges Person 4's `install_provider_payment` settlement side-channel
(the `PAYMENT-RESPONSE` header) into the frozen contract's response body.

`packages/payments` settles payment and adds a `PAYMENT-RESPONSE` header to
the route's response *after* the route handler already returned -- it does
not hand the settlement receipt (transaction hash, payer) to the route
handler directly. But the frozen `Reservation` and `DeliveryBooking`
schemas require a full `paymentReceipt` object embedded in the response
*body*. This module is the seam that reconciles the two: an outer
Starlette middleware, registered after every `install_provider_payment`
call, that reads the header once settlement succeeds, patches the real
transaction hash and payer into the already-built response body, and
persists them to the matching DB row.

Route handlers build their initial response with `PENDING_TRANSACTION` and
`PENDING_PAYER` placeholders in `paymentReceipt`; this middleware turns
them into the real, validated values before the response reaches the
client. It never touches `packages/payments/**`.
"""

from __future__ import annotations

import base64
import json
import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

PENDING_TRANSACTION = "F" * 64
PENDING_PAYER = "rPendingSettXn1111111111111111"

PersistReceipt = Callable[[str, str, str, str], None]
"""`(resource_id, transaction, payer, explorer_url) -> None`."""


def explorer_url(transaction: str) -> str:
    return f"https://testnet.xrpl.org/transactions/{transaction}"


def install_receipt_bridge(app: FastAPI, *, id_field: str, persist_receipt: PersistReceipt) -> None:
    """Register the settlement-receipt bridge once per provider app.

    Must be added *after* every `install_provider_payment(...)` call for
    that app so it wraps them -- Starlette runs the most-recently-added
    middleware outermost, so this is the layer that sees the
    `PAYMENT-RESPONSE` header those calls add to a successful response.
    """

    @app.middleware("http")
    async def _embed_settlement_receipt(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        response = await call_next(request)

        payment_response_header = response.headers.get("payment-response")
        if not payment_response_header or response.status_code >= 400:
            return response

        body = b"".join([chunk async for chunk in response.body_iterator])
        headers = dict(response.headers)
        headers.pop("content-length", None)

        try:
            payload = json.loads(body)
            settle = json.loads(base64.b64decode(payment_response_header))
            transaction = str(settle["transaction"]).upper()
            payer = str(settle["payer"])
            url = explorer_url(transaction)
            receipt = payload.get("paymentReceipt")
            if isinstance(receipt, dict):
                receipt["transaction"] = transaction
                receipt["payer"] = payer
                receipt["explorerUrl"] = url
                resource_id = payload.get(id_field)
                if resource_id:
                    persist_receipt(resource_id, transaction, payer, url)
            body = json.dumps(payload).encode("utf-8")
        except Exception:  # noqa: BLE001
            logger.exception("failed to embed settlement receipt into response body")

        return Response(
            content=body,
            status_code=response.status_code,
            headers=headers,
            media_type="application/json",
        )
