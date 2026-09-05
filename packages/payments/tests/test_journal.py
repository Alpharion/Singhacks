from __future__ import annotations

import pytest

from surplusflow_payments.errors import (
    DuplicatePaymentError,
    PaymentInProgressError,
)
from surplusflow_payments.journal import PaymentJournal
from surplusflow_payments.models import JournalStatus

from conftest import SECOND_PAYEE, make_intent

TX_HASH = "A" * 64


def test_journal_records_complete_payment_lifecycle(tmp_path, intent) -> None:
    journal = PaymentJournal(tmp_path / "payments.sqlite3")

    journal.begin(intent)
    assert journal.get(intent.invoice_id).status is JournalStatus.PENDING

    journal.record_signed(intent.invoice_id, TX_HASH.lower())
    signed = journal.get(intent.invoice_id)
    assert signed.status is JournalStatus.SIGNED
    assert signed.transaction_hash == TX_HASH

    journal.record_validated(intent.invoice_id, TX_HASH.lower())
    validated = journal.get(intent.invoice_id)
    assert validated.status is JournalStatus.VALIDATED
    assert validated.error_code is None

    with pytest.raises(DuplicatePaymentError, match="already been paid"):
        journal.begin(intent)


@pytest.mark.parametrize(
    "status_method",
    ["pending", "signed", "uncertain"],
)
def test_journal_blocks_unsafe_resubmission(
    tmp_path,
    intent,
    status_method: str,
) -> None:
    journal = PaymentJournal(tmp_path / f"{status_method}.sqlite3")
    journal.begin(intent)
    if status_method == "signed":
        journal.record_signed(intent.invoice_id, TX_HASH)
    elif status_method == "uncertain":
        journal.record_uncertain(intent.invoice_id, TX_HASH, "timeout")

    with pytest.raises(PaymentInProgressError, match="reconciliation"):
        journal.begin(intent)


def test_failed_attempt_can_be_retried(tmp_path, intent) -> None:
    journal = PaymentJournal(tmp_path / "payments.sqlite3")
    journal.begin(intent)
    journal.record_failed(intent.invoice_id, "provider_unavailable")

    journal.begin(intent)

    entry = journal.get(intent.invoice_id)
    assert entry.status is JournalStatus.PENDING
    assert entry.transaction_hash is None
    assert entry.error_code is None


@pytest.mark.parametrize(
    "changed_intent",
    [
        make_intent(payTo=SECOND_PAYEE),
        make_intent(amountDrops="1"),
        make_intent(invoiceId="inv:different_001"),
        make_intent(idempotencyKey="idem:different_001"),
    ],
)
def test_rejects_reused_identity_with_different_terms(
    tmp_path,
    intent,
    changed_intent,
) -> None:
    journal = PaymentJournal(tmp_path / "payments.sqlite3")
    journal.begin(intent)

    with pytest.raises(DuplicatePaymentError, match="different payment terms"):
        journal.begin(changed_intent)


def test_unknown_invoice_transition_fails(tmp_path) -> None:
    journal = PaymentJournal(tmp_path / "payments.sqlite3")

    with pytest.raises(KeyError, match="unknown invoice"):
        journal.record_failed("inv:missing_001", "missing")

    assert journal.get("inv:missing_001") is None
