class PaymentError(RuntimeError):
    """Base class for sanitized payment-boundary failures."""

    code = "payment_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)


class WalletConfigurationError(PaymentError):
    code = "wallet_configuration_error"


class PolicyViolation(PaymentError):
    code = "policy_rejected"


class DuplicatePaymentError(PaymentError):
    code = "payment_replayed"


class PaymentInProgressError(PaymentError):
    code = "payment_in_progress"


class PaymentExecutionError(PaymentError):
    code = "payment_failed"


class PaymentReceiptError(PaymentError):
    code = "invalid_payment_receipt"
