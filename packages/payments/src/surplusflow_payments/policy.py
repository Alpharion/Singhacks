from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from .errors import PolicyViolation
from .models import PaymentRequirementOption, PurchaseIntent


class PaymentPolicy:
    """Deterministic authorization checks executed before any signing call."""

    def __init__(
        self,
        *,
        expected_source_tag: int = 20_260_530,
        system_max_order_spend_drops: int | None = None,
        system_max_transaction_spend_drops: int | None = None,
    ) -> None:
        self.expected_source_tag = expected_source_tag
        self.system_max_order_spend_drops = system_max_order_spend_drops
        self.system_max_transaction_spend_drops = (
            system_max_transaction_spend_drops
        )

    def validate_intent(
        self,
        intent: PurchaseIntent,
        *,
        already_spent_drops: int,
        now: datetime | None = None,
    ) -> None:
        current_time = now or datetime.now(UTC)
        if intent.expires_at <= current_time:
            raise PolicyViolation("purchase intent has expired")
        if intent.pay_to not in intent.policy_snapshot.allowed_payees:
            raise PolicyViolation("recipient is not in the wallet-policy allowlist")
        if already_spent_drops < 0:
            raise PolicyViolation("already-spent amount cannot be negative")

        amount = int(intent.amount_drops)
        declared_transaction_cap = int(
            intent.policy_snapshot.max_transaction_spend_drops
        )
        declared_order_cap = int(intent.policy_snapshot.max_order_spend_drops)
        if (
            self.system_max_transaction_spend_drops is not None
            and declared_transaction_cap > self.system_max_transaction_spend_drops
        ):
            raise PolicyViolation(
                "purchase intent exceeds the system transaction-policy ceiling"
            )
        if (
            self.system_max_order_spend_drops is not None
            and declared_order_cap > self.system_max_order_spend_drops
        ):
            raise PolicyViolation(
                "purchase intent exceeds the system order-policy ceiling"
            )
        transaction_cap = min(
            declared_transaction_cap,
            self.system_max_transaction_spend_drops
            if self.system_max_transaction_spend_drops is not None
            else declared_transaction_cap,
        )
        order_cap = min(
            declared_order_cap,
            self.system_max_order_spend_drops
            if self.system_max_order_spend_drops is not None
            else declared_order_cap,
        )
        if amount > transaction_cap:
            raise PolicyViolation("payment exceeds the per-transaction cap")
        if already_spent_drops + amount > order_cap:
            raise PolicyViolation("payment would exceed the total order cap")

    def authorize(
        self,
        intent: PurchaseIntent,
        requirement: PaymentRequirementOption,
        *,
        already_spent_drops: int,
        now: datetime | None = None,
    ) -> None:
        self.validate_intent(
            intent,
            already_spent_drops=already_spent_drops,
            now=now,
        )
        if requirement.network != intent.network:
            raise PolicyViolation("x402 network does not match purchase intent")
        if requirement.asset != intent.asset:
            raise PolicyViolation("x402 asset does not match purchase intent")
        if requirement.pay_to != intent.pay_to:
            raise PolicyViolation("x402 recipient does not match purchase intent")
        if requirement.amount != intent.amount_drops:
            raise PolicyViolation("x402 amount does not match purchase intent")
        if requirement.extra.invoice_id != intent.invoice_id:
            raise PolicyViolation("x402 invoice does not match purchase intent")
        if requirement.extra.source_tag != self.expected_source_tag:
            raise PolicyViolation("x402 SourceTag does not match project attribution")

    def selector(
        self,
        intent: PurchaseIntent,
        *,
        already_spent_drops: int,
        now: datetime | None = None,
    ):
        """Return an x402 SDK selector that accepts only an authorized option."""

        def select(
            accepts: Sequence[Mapping[str, Any]],
            network_filter: str | None = None,
            scheme_filter: str | None = None,
            max_value: Any | None = None,
        ) -> Mapping[str, Any]:
            del network_filter, scheme_filter, max_value
            reasons: list[str] = []
            for raw in accepts:
                try:
                    requirement = PaymentRequirementOption.model_validate(raw)
                    self.authorize(
                        intent,
                        requirement,
                        already_spent_drops=already_spent_drops,
                        now=now,
                    )
                except (ValidationError, PolicyViolation) as exc:
                    reasons.append(str(exc))
                    continue
                return raw
            summary = reasons[0] if reasons else "no payment options were provided"
            raise PolicyViolation(f"no authorized x402 option: {summary}")

        return select
