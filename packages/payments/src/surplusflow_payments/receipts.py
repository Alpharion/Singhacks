from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Mapping

from .errors import PaymentReceiptError
from .models import PaymentReceipt, PurchaseIntent, WirePaymentResponse


def normalize_payment_receipt(
    wire_value: Mapping[str, Any],
    intent: PurchaseIntent,
    *,
    expected_payer: str,
    persisted_transaction_hash: str | None = None,
    validated_at: datetime | None = None,
) -> PaymentReceipt:
    try:
        wire = WirePaymentResponse.model_validate(wire_value)
    except Exception:
        raise PaymentReceiptError("PAYMENT-RESPONSE is malformed") from None

    if wire.payer != expected_payer:
        raise PaymentReceiptError("PAYMENT-RESPONSE payer does not match buyer wallet")
    if wire.network != intent.network:
        raise PaymentReceiptError("PAYMENT-RESPONSE network does not match intent")
    transaction_hash = wire.transaction.upper()
    if (
        persisted_transaction_hash is not None
        and transaction_hash != persisted_transaction_hash.upper()
    ):
        raise PaymentReceiptError(
            "PAYMENT-RESPONSE transaction does not match the pre-submission hash"
        )

    return PaymentReceipt(
        transaction=transaction_hash,
        network=wire.network,
        payer=wire.payer,
        payee=intent.pay_to,
        amount_drops=intent.amount_drops,
        invoice_id=intent.invoice_id,
        validated_at=validated_at or datetime.now(UTC),
        explorer_url=(
            "https://testnet.xrpl.org/transactions/" + transaction_hash
        ),
    )
