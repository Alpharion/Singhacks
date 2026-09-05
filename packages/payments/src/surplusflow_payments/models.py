from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
)
from xrpl.core.addresscodec import is_valid_classic_address


def to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


def validate_classic_address(value: str) -> str:
    if not is_valid_classic_address(value):
        raise ValueError("must be a valid XRPL classic address")
    return value


class ContractModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
        extra="forbid",
    )


class PaymentPolicySnapshot(ContractModel):
    wallet_policy_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,63}$")
    max_order_spend_drops: str = Field(pattern=r"^[1-9][0-9]*$")
    max_transaction_spend_drops: str = Field(pattern=r"^[1-9][0-9]*$")
    allowed_payees: list[str] = Field(min_length=1)

    _validate_payees = field_validator("allowed_payees")(
        lambda values: [validate_classic_address(value) for value in values]
    )


class PurchaseIntent(ContractModel):
    intent_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,63}$")
    run_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,63}$")
    goal_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,63}$")
    resource_type: Literal["food_reservation", "delivery_booking"]
    provider_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,63}$")
    resource_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,63}$")
    target_url: HttpUrl
    quantity: int | None = Field(default=None, ge=1)
    amount_drops: str = Field(pattern=r"^[1-9][0-9]*$")
    pay_to: str
    network: Literal["xrpl:1"]
    asset: Literal["XRP"]
    invoice_id: str = Field(pattern=r"^[A-Za-z0-9._:-]{8,128}$")
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9._:-]{8,128}$")
    expires_at: AwareDatetime
    rationale: str = Field(min_length=1, max_length=1000)
    policy_snapshot: PaymentPolicySnapshot

    _validate_pay_to = field_validator("pay_to")(validate_classic_address)


class PaymentRequirementExtra(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    invoice_id: str = Field(alias="invoiceId", pattern=r"^[A-Za-z0-9._:-]{8,128}$")
    source_tag: int = Field(alias="sourceTag", ge=0, le=4_294_967_295)
    destination_tag: int | None = Field(
        default=None,
        alias="destinationTag",
        ge=0,
        le=4_294_967_295,
    )


class PaymentRequirementOption(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    scheme: Literal["exact"]
    network: Literal["xrpl:1"]
    asset: Literal["XRP"]
    pay_to: str = Field(alias="payTo")
    amount: str = Field(pattern=r"^[1-9][0-9]*$")
    max_timeout_seconds: int = Field(alias="maxTimeoutSeconds", ge=1, le=3600)
    extra: PaymentRequirementExtra

    _validate_pay_to = field_validator("pay_to")(validate_classic_address)


class PaymentRequiredChallenge(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    x402_version: Literal[2] = Field(alias="x402Version")
    accepts: list[PaymentRequirementOption] = Field(min_length=1)


class WirePaymentResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    success: Literal[True]
    transaction: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")
    network: Literal["xrpl:1"]
    payer: str

    _validate_payer = field_validator("payer")(validate_classic_address)


class PaymentReceipt(ContractModel):
    success: Literal[True] = True
    transaction: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")
    network: Literal["xrpl:1"]
    payer: str
    payee: str
    amount_drops: str = Field(pattern=r"^[1-9][0-9]*$")
    invoice_id: str = Field(pattern=r"^[A-Za-z0-9._:-]{8,128}$")
    validated: Literal[True] = True
    validated_at: AwareDatetime
    explorer_url: HttpUrl

    _validate_payer = field_validator("payer")(validate_classic_address)
    _validate_payee = field_validator("payee")(validate_classic_address)


class PaymentExecutionResult(ContractModel):
    receipt: PaymentReceipt
    status_code: int = Field(ge=200, lt=300)
    resource: Any


class JournalStatus(StrEnum):
    PENDING = "pending"
    SIGNED = "signed"
    VALIDATED = "validated"
    FAILED = "failed"
    UNCERTAIN = "uncertain"


class PaymentJournalEntry(ContractModel):
    invoice_id: str
    idempotency_key: str
    status: JournalStatus
    payee: str
    amount_drops: str
    transaction_hash: str | None = None
    error_code: str | None = None
    created_at: datetime
    updated_at: datetime
