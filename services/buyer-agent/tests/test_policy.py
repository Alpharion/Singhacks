from __future__ import annotations

from buyer_agent.config import Settings
from buyer_agent.policy import authorize, load_policy

PAYEE = "rFoodA1111111111111111111111111"
STRANGER = "rStranger11111111111111111111"


def settings_with(**kwargs) -> Settings:
    return Settings(**kwargs)


def test_order_cap_never_exceeds_the_stated_budget():
    policy = load_policy("policy_demo_001", "120000000", settings_with())
    assert policy.max_order_spend_drops == 120_000_000
    # A generous wallet ceiling cannot widen the authority the buyer delegated.
    assert policy.max_transaction_spend_drops <= policy.max_order_spend_drops


def test_a_payment_within_every_limit_is_authorized():
    policy = load_policy("policy_demo_001", "120000000", settings_with())
    assert (
        authorize(policy, amount_drops=36_000_000, pay_to=PAYEE, already_spent_drops=0)
        is None
    )


def test_an_unknown_payee_is_refused():
    policy = load_policy("policy_demo_001", "120000000", settings_with())
    rejection = authorize(
        policy, amount_drops=1_000_000, pay_to=STRANGER, already_spent_drops=0
    )
    assert rejection is not None
    assert rejection.error == "policy_rejected"
    assert "approved payee list" in rejection.reason


def test_the_per_transaction_cap_is_enforced():
    policy = load_policy("policy_demo_001", "120000000", settings_with())
    rejection = authorize(
        policy, amount_drops=100_000_000, pay_to=PAYEE, already_spent_drops=0
    )
    assert rejection is not None
    assert rejection.error == "policy_rejected"
    assert "per-transaction limit" in rejection.reason


def test_the_order_budget_is_enforced_across_payments():
    policy = load_policy("policy_demo_001", "120000000", settings_with())
    rejection = authorize(
        policy, amount_drops=60_000_000, pay_to=PAYEE, already_spent_drops=70_000_000
    )
    assert rejection is not None
    assert rejection.error == "budget_exceeded"


def test_delivery_budget_is_protected_from_being_spent_on_food():
    policy = load_policy("policy_demo_001", "70000000", settings_with())
    rejection = authorize(
        policy,
        amount_drops=65_000_000,
        pay_to=PAYEE,
        already_spent_drops=0,
        reserve_drops=12_000_000,
    )
    assert rejection is not None
    assert rejection.error == "budget_exceeded"
    assert "delivery already planned" in rejection.reason


def test_a_zero_payment_is_refused():
    policy = load_policy("policy_demo_001", "120000000", settings_with())
    assert authorize(policy, amount_drops=0, pay_to=PAYEE, already_spent_drops=0) is not None


def test_the_snapshot_carries_the_limits_to_the_payment_boundary():
    policy = load_policy("policy_demo_001", "120000000", settings_with())
    snapshot = policy.snapshot()
    assert snapshot.max_order_spend_drops == "120000000"
    assert PAYEE in snapshot.allowed_payees
