from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from xrpl.clients import JsonRpcClient
from xrpl.models.requests import Tx

from .errors import PaymentExecutionError


@dataclass(frozen=True)
class TransactionStatus:
    transaction_hash: str
    validated: bool
    result_code: str | None
    ledger_index: int | None


class TransactionStatusClient:
    def __init__(self, rpc_url: str, *, client: Any | None = None) -> None:
        self.client = client or JsonRpcClient(rpc_url)

    def get(self, transaction_hash: str) -> TransactionStatus:
        try:
            response = self.client.request(Tx(transaction=transaction_hash))
            result = response.result
        except Exception:
            raise PaymentExecutionError(
                "could not retrieve the XRPL transaction status"
            ) from None

        meta = result.get("meta")
        result_code = (
            meta.get("TransactionResult") if isinstance(meta, dict) else None
        )
        ledger_index = result.get("ledger_index")
        return TransactionStatus(
            transaction_hash=transaction_hash.upper(),
            validated=bool(result.get("validated", False)),
            result_code=str(result_code) if result_code is not None else None,
            ledger_index=int(ledger_index) if ledger_index is not None else None,
        )
