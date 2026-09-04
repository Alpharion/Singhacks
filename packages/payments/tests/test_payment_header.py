from __future__ import annotations

import base64
import json

import pytest
from xrpl.core.binarycodec import encode
from xrpl.models.transactions import Payment
from xrpl.transaction import sign
from x402_xrpl.types import PaymentRequirements

from surplusflow_payments.errors import PaymentExecutionError
from surplusflow_payments.journal import PaymentJournal
from surplusflow_payments.models import JournalStatus
from surplusflow_payments.payment_header import (
    PersistingPaymentHeaderFactory,
    transaction_hash_from_payment_header,
)

from conftest import PAYEE, SOURCE_TAG


def signed_header(wallet) -> tuple[str, str]:
    transaction = Payment(
        account=wallet.classic_address,
        destination=PAYEE,
        amount="1",
        fee="12",
        sequence=1,
        last_ledger_sequence=100,
        source_tag=SOURCE_TAG,
    )
    signed = sign(transaction, wallet)
    payload = {
        "x402Version": 2,
        "payload": {"signedTxBlob": encode(signed.to_xrpl())},
    }
    header = base64.b64encode(json.dumps(payload).encode()).decode()
    return header, signed.get_hash().upper()


def requirement() -> PaymentRequirements:
    return PaymentRequirements(
        scheme="exact",
        network="xrpl:1",
        amount="1",
        asset="XRP",
        pay_to=PAYEE,
        max_timeout_seconds=600,
        extra={"invoiceId": "inv:header_001", "sourceTag": SOURCE_TAG},
    )


def test_extracts_transaction_hash_without_submitting(buyer_wallet) -> None:
    header, expected_hash = signed_header(buyer_wallet)

    assert transaction_hash_from_payment_header(header) == expected_hash


def test_persists_hash_before_returning_header(
    tmp_path,
    intent,
    buyer_wallet,
) -> None:
    journal = PaymentJournal(tmp_path / "payments.sqlite3")
    journal.begin(intent)
    header, expected_hash = signed_header(buyer_wallet)
    observed_statuses: list[JournalStatus] = []

    def delegate(_requirement, *, extensions=None) -> str:
        del extensions
        observed_statuses.append(journal.get(intent.invoice_id).status)
        return header

    factory = PersistingPaymentHeaderFactory(
        delegate,
        journal,
        intent.invoice_id,
    )

    assert factory(requirement()) == header
    assert observed_statuses == [JournalStatus.PENDING]
    assert factory.transaction_hash == expected_hash
    assert journal.get(intent.invoice_id).status is JournalStatus.SIGNED


def test_rejects_unreadable_signed_payload() -> None:
    with pytest.raises(PaymentExecutionError, match="unreadable"):
        transaction_hash_from_payment_header("not-a-payment")
