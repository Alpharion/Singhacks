from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from surplusflow_payments.errors import PolicyViolation
from surplusflow_payments.models import PaymentRequirementOption
from surplusflow_payments.policy import PaymentPolicy

from conftest import PAYEE, SECOND_PAYEE, make_intent, requirement_dict


def test_authorizes_exact_preapproved_requirement(intent) -> None:
    policy = PaymentPolicy(
        system_max_order_spend_drops=120_000_000,
        system_max_transaction_spend_drops=70_000_000,
    )
    requirement = PaymentRequirementOption.model_validate(
        requirement_dict(intent)
    )

    policy.authorize(intent, requirement, already_spent_drops=10_000_000)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("payTo", SECOND_PAYEE, "recipient"),
        ("amount", "36000001", "amount"),
        (
            "extra",
            {"invoiceId": "inv:different_001", "sourceTag": 20_260_530},
            "invoice",
        ),
        (
            "extra",
            {"invoiceId": "inv:run_demo_001:offer_demo_001:v1", "sourceTag": 1},
            "SourceTag",
        ),
    ],
)
def test_rejects_requirement_that_changes_authorized_terms(
    intent,
    field: str,
    value: object,
    message: str,
) -> None:
    policy = PaymentPolicy()
    requirement = PaymentRequirementOption.model_validate(
        requirement_dict(intent, **{field: value})
    )

    with pytest.raises(PolicyViolation, match=message):
        policy.authorize(intent, requirement, already_spent_drops=0)


def test_rejects_expired_intent() -> None:
    intent = make_intent(expiresAt=datetime.now(UTC) - timedelta(seconds=1))

    with pytest.raises(PolicyViolation, match="expired"):
        PaymentPolicy().validate_intent(intent, already_spent_drops=0)


def test_rejects_recipient_outside_allowlist() -> None:
    intent = make_intent(
        policySnapshot={
            "walletPolicyId": "policy_demo_001",
            "maxOrderSpendDrops": "120000000",
            "maxTransactionSpendDrops": "70000000",
            "allowedPayees": [SECOND_PAYEE],
        }
    )

    with pytest.raises(PolicyViolation, match="allowlist"):
        PaymentPolicy().validate_intent(intent, already_spent_drops=0)


@pytest.mark.parametrize(
    ("already_spent", "amount", "message"),
    [
        (-1, "36000000", "negative"),
        (0, "70000001", "per-transaction"),
        (90_000_000, "36000000", "total order"),
    ],
)
def test_enforces_budget_limits(
    already_spent: int,
    amount: str,
    message: str,
) -> None:
    intent = make_intent(amountDrops=amount)
    policy = PaymentPolicy(
        system_max_order_spend_drops=120_000_000,
        system_max_transaction_spend_drops=70_000_000,
    )

    with pytest.raises(PolicyViolation, match=message):
        policy.validate_intent(intent, already_spent_drops=already_spent)


@pytest.mark.parametrize(
    ("policy_snapshot", "message"),
    [
        (
            {
                "walletPolicyId": "policy_demo_001",
                "maxOrderSpendDrops": "120000001",
                "maxTransactionSpendDrops": "70000000",
                "allowedPayees": [PAYEE],
            },
            "order-policy ceiling",
        ),
        (
            {
                "walletPolicyId": "policy_demo_001",
                "maxOrderSpendDrops": "120000000",
                "maxTransactionSpendDrops": "70000001",
                "allowedPayees": [PAYEE],
            },
            "transaction-policy ceiling",
        ),
    ],
)
def test_rejects_intent_that_weakens_system_policy(
    policy_snapshot: dict[str, object],
    message: str,
) -> None:
    intent = make_intent(policySnapshot=policy_snapshot)
    policy = PaymentPolicy(
        system_max_order_spend_drops=120_000_000,
        system_max_transaction_spend_drops=70_000_000,
    )

    with pytest.raises(PolicyViolation, match=message):
        policy.validate_intent(intent, already_spent_drops=0)


def test_selector_skips_invalid_option_and_returns_exact_match(intent) -> None:
    wrong = requirement_dict(intent, payTo=SECOND_PAYEE)
    valid = requirement_dict(intent)

    selected = PaymentPolicy().selector(
        intent,
        already_spent_drops=0,
    )([wrong, valid])

    assert selected is valid


def test_selector_rejects_empty_options(intent) -> None:
    selector = PaymentPolicy().selector(intent, already_spent_drops=0)

    with pytest.raises(PolicyViolation, match="no payment options"):
        selector([])
