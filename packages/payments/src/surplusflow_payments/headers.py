import base64
import json

from .errors import PaymentExecutionError
from .models import PaymentRequiredChallenge


def decode_payment_required(header_value: str) -> PaymentRequiredChallenge:
    try:
        decoded = json.loads(base64.b64decode(header_value, validate=True))
        return PaymentRequiredChallenge.model_validate(decoded)
    except Exception:
        raise PaymentExecutionError(
            "PAYMENT-REQUIRED is not valid base64-encoded x402 v2 JSON"
        ) from None
