from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import requests
from xrpl.wallet import Wallet
from x402_xrpl.client import (
    XRPLPresignedPaymentPayer,
    XRPLPresignedPaymentPayerOptions,
)
from x402_xrpl.clients import X402PurchaseResult, x402_purchase

from .config import PaymentSettings
from .errors import (
    PaymentError,
    PaymentExecutionError,
    PaymentReceiptError,
    PolicyViolation,
    WalletConfigurationError,
)
from .journal import PaymentJournal
from .models import PaymentExecutionResult, PurchaseIntent
from .payment_header import PersistingPaymentHeaderFactory
from .policy import PaymentPolicy
from .receipts import normalize_payment_receipt
from .wallet import load_buyer_wallet

WalletLoader = Callable[[], Wallet]
PurchaseFunction = Callable[..., X402PurchaseResult]
PayerFactory = Callable[[Wallet, str, str], Any]


def _default_payer_factory(
    wallet: Wallet,
    network: str,
    rpc_url: str,
) -> XRPLPresignedPaymentPayer:
    return XRPLPresignedPaymentPayer(
        XRPLPresignedPaymentPayerOptions(
            wallet=wallet,
            network=network,
            rpc_url=rpc_url,
            invoice_binding="both",
        )
    )


class PaymentExecutor:
    """Execute one pre-authorized x402 purchase inside deterministic limits."""

    def __init__(
        self,
        settings: PaymentSettings,
        journal: PaymentJournal,
        *,
        wallet_loader: WalletLoader = load_buyer_wallet,
        purchase_function: PurchaseFunction = x402_purchase,
        payer_factory: PayerFactory = _default_payer_factory,
    ) -> None:
        self.settings = settings
        self.journal = journal
        self.wallet_loader = wallet_loader
        self.purchase_function = purchase_function
        self.payer_factory = payer_factory
        self.policy = PaymentPolicy(
            expected_source_tag=settings.xrpl_source_tag,
            system_max_order_spend_drops=settings.max_order_spend_drops,
            system_max_transaction_spend_drops=(
                settings.max_transaction_spend_drops
            ),
        )

    def execute(
        self,
        intent: PurchaseIntent,
        *,
        already_spent_drops: int,
        request_body: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        session: requests.Session | None = None,
        timeout_seconds: float = 30,
    ) -> PaymentExecutionResult:
        self.policy.validate_intent(
            intent,
            already_spent_drops=already_spent_drops,
        )
        self.journal.begin(intent)

        try:
            wallet = self.wallet_loader()
        except Exception as exc:
            self.journal.record_failed(intent.invoice_id, "wallet_configuration_error")
            if isinstance(exc, PaymentError):
                raise
            raise WalletConfigurationError(
                "buyer wallet could not be loaded"
            ) from None

        payer_address = wallet.classic_address
        try:
            payer = self.payer_factory(
                wallet,
                self.settings.xrpl_network,
                self.settings.rpc_url,
            )
        except Exception:
            self.journal.record_failed(intent.invoice_id, "payer_configuration_error")
            raise PaymentExecutionError(
                "x402 payer could not be configured"
            ) from None
        persisting_factory = PersistingPaymentHeaderFactory(
            payer.create_payment_header,
            self.journal,
            intent.invoice_id,
        )

        outbound_headers = dict(headers or {})
        if any(key.lower() == "payment-signature" for key in outbound_headers):
            self.journal.record_failed(intent.invoice_id, "caller_payment_header")
            raise PolicyViolation("caller must not supply PAYMENT-SIGNATURE")
        supplied_idempotency_key = next(
            (
                value
                for key, value in outbound_headers.items()
                if key.lower() == "idempotency-key"
            ),
            None,
        )
        if (
            supplied_idempotency_key is not None
            and supplied_idempotency_key != intent.idempotency_key
        ):
            self.journal.record_failed(
                intent.invoice_id,
                "caller_idempotency_mismatch",
            )
            raise PolicyViolation(
                "caller Idempotency-Key does not match purchase intent"
            )
        outbound_headers = {
            key: value
            for key, value in outbound_headers.items()
            if key.lower() != "idempotency-key"
        }
        outbound_headers["Idempotency-Key"] = intent.idempotency_key

        request_kwargs: dict[str, Any] = {
            "json": dict(request_body)
            if request_body is not None
            else intent.model_dump(mode="json", by_alias=True),
            "timeout": timeout_seconds,
        }
        if session is not None:
            request_kwargs["session"] = session

        try:
            result = self.purchase_function(
                str(intent.target_url),
                wallet=wallet,
                rpc_url=self.settings.rpc_url,
                method="POST",
                headers=outbound_headers,
                payment_requirements_selector=self.policy.selector(
                    intent,
                    already_spent_drops=already_spent_drops,
                ),
                network_filter=self.settings.xrpl_network,
                scheme_filter="exact",
                max_value=int(intent.amount_drops),
                invoice_binding="both",
                payment_header_factory=persisting_factory,
                confirmation_mode="auto",
                user_intent=intent.rationale,
                **request_kwargs,
            )
        except Exception:
            self._record_unsuccessful(intent, persisting_factory, "client_exception")
            raise PaymentExecutionError("x402 client execution failed") from None

        if result.status != "success" or result.response is None:
            self._record_unsuccessful(
                intent,
                persisting_factory,
                f"x402_{result.status}",
            )
            raise PaymentExecutionError(
                f"x402 purchase did not settle successfully ({result.status})"
            )
        if result.payment_response is None:
            self._record_unsuccessful(
                intent,
                persisting_factory,
                "missing_payment_response",
            )
            raise PaymentReceiptError(
                "paid endpoint returned no PAYMENT-RESPONSE settlement receipt"
            )

        try:
            receipt = normalize_payment_receipt(
                result.payment_response,
                intent,
                expected_payer=payer_address,
                persisted_transaction_hash=persisting_factory.transaction_hash,
            )
        except PaymentReceiptError:
            self._record_unsuccessful(
                intent,
                persisting_factory,
                "invalid_payment_receipt",
            )
            raise

        self.journal.record_validated(intent.invoice_id, receipt.transaction)

        try:
            resource: Any = result.response.json()
        except Exception:
            resource = result.response.text
        return PaymentExecutionResult(
            receipt=receipt,
            status_code=result.response.status_code,
            resource=resource,
        )

    def _record_unsuccessful(
        self,
        intent: PurchaseIntent,
        factory: PersistingPaymentHeaderFactory,
        error_code: str,
    ) -> None:
        if factory.transaction_hash is None:
            self.journal.record_failed(intent.invoice_id, error_code)
            return
        self.journal.record_uncertain(
            intent.invoice_id,
            factory.transaction_hash,
            error_code,
        )
