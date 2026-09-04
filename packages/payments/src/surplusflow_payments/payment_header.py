from __future__ import annotations

import base64
import json
from collections.abc import Callable, Mapping
from typing import Any

from xrpl.core.binarycodec import decode
from xrpl.models.transactions import Transaction
from x402_xrpl.types import PaymentRequirements

from .errors import PaymentExecutionError
from .journal import PaymentJournal

PaymentHeaderDelegate = Callable[..., str]


def transaction_hash_from_payment_header(header_value: str) -> str:
    """Recover the XRPL hash without logging or persisting the signed blob."""

    try:
        decoded_header = json.loads(base64.b64decode(header_value))
        signed_blob = decoded_header["payload"]["signedTxBlob"]
        transaction_json = decode(signed_blob)
        transaction = Transaction.from_xrpl(transaction_json)
        return transaction.get_hash().upper()
    except Exception:
        raise PaymentExecutionError(
            "x402 generated an unreadable signed payment payload"
        ) from None


class PersistingPaymentHeaderFactory:
    """Persist the transaction hash before x402 sends the paid retry."""

    def __init__(
        self,
        delegate: PaymentHeaderDelegate,
        journal: PaymentJournal,
        invoice_id: str,
    ) -> None:
        self.delegate = delegate
        self.journal = journal
        self.invoice_id = invoice_id
        self.transaction_hash: str | None = None

    def __call__(
        self,
        requirement: PaymentRequirements,
        *,
        extensions: Mapping[str, Any] | None = None,
    ) -> str:
        header = self.delegate(requirement, extensions=extensions)
        transaction_hash = transaction_hash_from_payment_header(header)
        self.journal.record_signed(self.invoice_id, transaction_hash)
        self.transaction_hash = transaction_hash
        return header
