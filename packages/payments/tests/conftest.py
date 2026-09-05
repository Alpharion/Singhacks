from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from xrpl.wallet import Wallet

from surplusflow_payments.models import PurchaseIntent

PAYEE = "rPEPPER7kfTD9w2To4CQk6UCfuHM9c6GDY"
SECOND_PAYEE = "rPT1Sjq2YGrBMTttX4GZHjKu9dyfzbpAYe"
KNOWN_ACCOUNT = "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh"
SOURCE_TAG = 20_260_530


@pytest.fixture
def buyer_wallet() -> Wallet:
    return Wallet.create()


@pytest.fixture
def intent() -> PurchaseIntent:
    return make_intent()


def make_intent(**overrides: object) -> PurchaseIntent:
    data: dict[str, object] = {
        "intentId": "intent_demo_001",
        "runId": "run_demo_001",
        "goalId": "goal_demo_001",
        "resourceType": "food_reservation",
        "providerId": "seller_demo_001",
        "resourceId": "offer_demo_001",
        "targetUrl": "http://localhost:8011/paid/demo",
        "quantity": 20,
        "amountDrops": "36000000",
        "payTo": PAYEE,
        "network": "xrpl:1",
        "asset": "XRP",
        "invoiceId": "inv:run_demo_001:offer_demo_001:v1",
        "idempotencyKey": "idem:run_demo_001:offer_demo_001:v1",
        "expiresAt": datetime.now(UTC) + timedelta(minutes=10),
        "rationale": "Best valid plan inside the authorized budget.",
        "policySnapshot": {
            "walletPolicyId": "policy_demo_001",
            "maxOrderSpendDrops": "120000000",
            "maxTransactionSpendDrops": "70000000",
            "allowedPayees": [PAYEE, SECOND_PAYEE],
        },
    }
    data.update(overrides)
    return PurchaseIntent.model_validate(data)


def requirement_dict(
    purchase_intent: PurchaseIntent,
    **overrides: object,
) -> dict[str, object]:
    value: dict[str, object] = {
        "scheme": "exact",
        "network": "xrpl:1",
        "asset": "XRP",
        "payTo": purchase_intent.pay_to,
        "amount": purchase_intent.amount_drops,
        "maxTimeoutSeconds": 600,
        "extra": {
            "invoiceId": purchase_intent.invoice_id,
            "sourceTag": SOURCE_TAG,
        },
    }
    value.update(overrides)
    return value
