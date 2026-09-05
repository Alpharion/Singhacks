from __future__ import annotations

from datetime import UTC, datetime

import pytest

from surplusflow_payments.errors import PaymentReceiptError
from surplusflow_payments.receipts import normalize_payment_receipt

from conftest import KNOWN_ACCOUNT

TX_HASH = "ABCDEF12" * 8


def wire_receipt(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "success": True,
        "transaction": TX_HASH.lower(),
        "network": "xrpl:1",
        "payer": KNOWN_ACCOUNT,
    }
    value.update(overrides)
    return value


def test_normalizes_validated_wire_receipt(intent) -> None:
    timestamp = datetime.now(UTC)

    receipt = normalize_payment_receipt(
        wire_receipt(),
        intent,
        expected_payer=KNOWN_ACCOUNT,
        persisted_transaction_hash=TX_HASH,
        validated_at=timestamp,
    )

    assert receipt.transaction == TX_HASH
    assert receipt.invoice_id == intent.invoice_id
    assert receipt.payee == intent.pay_to
    assert receipt.amount_drops == intent.amount_drops
    assert receipt.validated_at == timestamp
    assert str(receipt.explorer_url).endswith(TX_HASH)


@pytest.mark.parametrize(
    ("wire", "expected_payer", "persisted_hash", "message"),
    [
        ({"success": False}, KNOWN_ACCOUNT, None, "malformed"),
        (wire_receipt(payer="rPEPPER7kfTD9w2To4CQk6UCfuHM9c6GDY"), KNOWN_ACCOUNT, None, "payer"),
        (wire_receipt(), KNOWN_ACCOUNT, "0" * 64, "pre-submission hash"),
    ],
)
def test_rejects_untrusted_receipt(
    intent,
    wire: dict[str, object],
    expected_payer: str,
    persisted_hash: str | None,
    message: str,
) -> None:
    with pytest.raises(PaymentReceiptError, match=message):
        normalize_payment_receipt(
            wire,
            intent,
            expected_payer=expected_payer,
            persisted_transaction_hash=persisted_hash,
        )
