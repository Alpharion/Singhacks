"""Deterministic spending authorization.

The language model never reaches this module. Every purchase must clear these
checks before a PurchaseIntent is built, and the intent carries a snapshot of
the policy so the payment boundary can re-validate the decoded x402 challenge
against the same numbers.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import drops
from .config import Settings
from .models import ErrorCode, PolicySnapshot


@dataclass(frozen=True)
class WalletPolicy:
    wallet_policy_id: str
    max_order_spend_drops: int
    max_transaction_spend_drops: int
    allowed_payees: tuple[str, ...]

    def snapshot(self) -> PolicySnapshot:
        return PolicySnapshot(
            wallet_policy_id=self.wallet_policy_id,
            max_order_spend_drops=drops.to_str(self.max_order_spend_drops),
            max_transaction_spend_drops=drops.to_str(self.max_transaction_spend_drops),
            allowed_payees=list(self.allowed_payees),
        )


@dataclass(frozen=True)
class PolicyRejection:
    error: ErrorCode
    reason: str


def load_policy(
    wallet_policy_id: str, goal_budget_drops: str, config: Settings
) -> WalletPolicy:
    """Resolve the delegated authority for a run.

    The order cap is the tighter of the user's stated budget and the configured
    wallet ceiling, so a generous request can never widen delegated authority.
    """
    configured_tx_cap = drops.to_int(config.max_transaction_spend_drops)
    order_cap = drops.to_int(goal_budget_drops)
    return WalletPolicy(
        wallet_policy_id=wallet_policy_id,
        max_order_spend_drops=order_cap,
        max_transaction_spend_drops=min(configured_tx_cap, order_cap),
        allowed_payees=tuple(config.allowed_payees),
    )


def authorize(
    policy: WalletPolicy,
    *,
    amount_drops: int,
    pay_to: str,
    already_spent_drops: int,
    reserve_drops: int = 0,
) -> PolicyRejection | None:
    """Return ``None`` when the payment is authorized, else why it is refused.

    ``reserve_drops`` is budget that must survive this payment, which is how the
    agent avoids spending its delivery money on food.
    """
    if amount_drops <= 0:
        return PolicyRejection("policy_rejected", "Payment amount must be positive.")
    if pay_to not in policy.allowed_payees:
        return PolicyRejection(
            "policy_rejected",
            f"Recipient {pay_to} is not on the approved payee list for this wallet policy.",
        )
    if amount_drops > policy.max_transaction_spend_drops:
        return PolicyRejection(
            "policy_rejected",
            f"{drops.to_xrp_label(amount_drops)} exceeds the "
            f"{drops.to_xrp_label(policy.max_transaction_spend_drops)} per-transaction limit.",
        )
    projected = already_spent_drops + amount_drops
    if projected > policy.max_order_spend_drops:
        return PolicyRejection(
            "budget_exceeded",
            f"Paying {drops.to_xrp_label(amount_drops)} would take total spend to "
            f"{drops.to_xrp_label(projected)}, above the "
            f"{drops.to_xrp_label(policy.max_order_spend_drops)} order budget.",
        )
    if projected + reserve_drops > policy.max_order_spend_drops:
        return PolicyRejection(
            "budget_exceeded",
            f"Paying {drops.to_xrp_label(amount_drops)} would leave too little to cover the "
            f"{drops.to_xrp_label(reserve_drops)} delivery already planned.",
        )
    return None
