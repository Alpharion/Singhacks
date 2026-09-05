import base64
import json

import pytest

from surplusflow_payments.errors import PaymentExecutionError
from surplusflow_payments.headers import decode_payment_required

from conftest import make_intent, requirement_dict


def encode_header(value: object) -> str:
    return base64.b64encode(json.dumps(value).encode()).decode()


def test_decodes_payment_required_header() -> None:
    intent = make_intent()
    challenge = decode_payment_required(
        encode_header({"x402Version": 2, "accepts": [requirement_dict(intent)]})
    )

    assert challenge.x402_version == 2
    assert challenge.accepts[0].extra.invoice_id == intent.invoice_id


@pytest.mark.parametrize("value", ["not-base64", encode_header({"bad": True})])
def test_rejects_bad_payment_required_header(value: str) -> None:
    with pytest.raises(PaymentExecutionError, match="PAYMENT-REQUIRED"):
        decode_payment_required(value)
