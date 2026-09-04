"""x402 payment-verification boundary.

Integration point for Person 4: `packages/payments` will publish the real
XRPL/x402 adapter. Until it ships, this module implements the SAME
interface (`PaymentAdapter`) behind an in-memory stub so the seller and
courier simulators can be built, tested, and demoed end-to-end now. Wiring
in the real adapter later is a one-line change in `get_payment_adapter()`
-- no router code changes, per
`docs/architecture/TEAM_READINESS.md`: "Person 3 implements the documented
provider endpoints and initially uses a payment-verification stub with the
exact Person 4 adapter interface."
"""

from __future__ import annotations

import base64
import json
import os
import secrets
from dataclasses import dataclass
from typing import Protocol

from .schemas import PaymentReceipt, PaymentRequirement
from .time_utils import now_utc, to_iso


class PaymentVerificationError(Exception):
    def __init__(self, error: str, message: str, retryable: bool) -> None:
        super().__init__(message)
        self.error = error
        self.message = message
        self.retryable = retryable


@dataclass(frozen=True)
class PendingPayment:
    pay_to: str
    amount_drops: str
    invoice_id: str
    source_tag: int
    max_timeout_seconds: int = 600


class PaymentAdapter(Protocol):
    """The adapter boundary Person 4's real `packages/payments` client will fill."""

    def build_requirement(self, pending: PendingPayment) -> PaymentRequirement: ...

    def verify_and_settle(self, payment_signature: str, pending: PendingPayment) -> PaymentReceipt: ...


def generate_source_tag() -> int:
    return secrets.randbelow(4_294_967_295) + 1


def encode_header(payload: dict) -> str:
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


def decode_header(header_value: str) -> dict:
    try:
        return json.loads(base64.b64decode(header_value))
    except Exception as exc:  # noqa: BLE001
        raise PaymentVerificationError(
            "payment_failed", "PAYMENT-SIGNATURE header is not valid base64-encoded JSON.", False
        ) from exc


_EXPLORER_BASE = os.environ.get("XRPL_EXPLORER_BASE_URL", "https://testnet.xrpl.org/transactions")
_BUYER_ADDRESS_FALLBACK = os.environ.get("XRPL_BUYER_ADDRESS_STUB", "rBuyer1111111111111111111111111")


class StubPaymentAdapter:
    """Deterministic in-process stand-in for the real XRPL/x402 adapter.

    It never touches the network or a wallet seed. It "settles" a payment
    once it receives a `PAYMENT-SIGNATURE` header that echoes back the
    exact requirement it issued (payTo, amount, invoiceId, network, asset),
    which is enough to exercise the full 402 -> sign -> retry -> 201 loop
    that the buyer agent, marketplace, and UI all depend on while Person 4
    builds the real settlement path.
    """

    def build_requirement(self, pending: PendingPayment) -> PaymentRequirement:
        return PaymentRequirement.model_validate(
            {
                "x402Version": 2,
                "accepts": [
                    {
                        "scheme": "exact",
                        "network": "xrpl:1",
                        "asset": "XRP",
                        "payTo": pending.pay_to,
                        "amount": pending.amount_drops,
                        "maxTimeoutSeconds": pending.max_timeout_seconds,
                        "extra": {
                            "invoiceId": pending.invoice_id,
                            "sourceTag": pending.source_tag,
                        },
                    }
                ],
            }
        )

    def verify_and_settle(self, payment_signature: str, pending: PendingPayment) -> PaymentReceipt:
        payload = decode_header(payment_signature)

        if payload.get("network") != "xrpl:1":
            raise PaymentVerificationError(
                "network_mismatch", f"Unsupported network {payload.get('network')!r}.", False
            )
        if payload.get("asset") != "XRP":
            raise PaymentVerificationError("network_mismatch", f"Unsupported asset {payload.get('asset')!r}.", False)
        if payload.get("payTo") != pending.pay_to:
            raise PaymentVerificationError(
                "payment_failed", "Payment recipient does not match the payment requirement.", False
            )
        if payload.get("amount") != pending.amount_drops:
            raise PaymentVerificationError(
                "payment_failed", "Payment amount does not match the payment requirement.", False
            )
        if payload.get("invoiceId") != pending.invoice_id:
            raise PaymentVerificationError("invoice_mismatch", "Invoice ID does not match this reservation.", False)

        transaction_hash = secrets.token_hex(32).upper()
        validated_at = now_utc()
        return PaymentReceipt.model_validate(
            {
                "success": True,
                "transaction": transaction_hash,
                "network": "xrpl:1",
                "payer": payload.get("payer", _BUYER_ADDRESS_FALLBACK),
                "payee": pending.pay_to,
                "amountDrops": pending.amount_drops,
                "invoiceId": pending.invoice_id,
                "validated": True,
                "validatedAt": to_iso(validated_at),
                "explorerUrl": f"{_EXPLORER_BASE}/{transaction_hash}",
            }
        )


def get_payment_adapter() -> PaymentAdapter:
    """Single seam to swap in Person 4's real `packages/payments` adapter.

    `packages/payments` does not exist yet. Once it ships, replace the
    return value below with that client; no caller in `services/marketplace`
    or `services/providers` should need to change.
    """

    return StubPaymentAdapter()
