from __future__ import annotations

import base64
import inspect
import json
import logging
import re
import uuid
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from x402_xrpl.facilitator import (
    AsyncFacilitatorClient,
    FacilitatorClientOptions,
)
from x402_xrpl.server import require_payment
from x402_xrpl.types import PaymentPayload

from .invoice_store import InvoiceRequestConflictError, SQLiteInvoiceStore
from .models import validate_classic_address
from .provider_idempotency import (
    ProviderIdempotencyMiddleware,
    ProviderRequestContext,
    SQLiteProviderResponseStore,
    current_provider_request,
    current_request_invoice_id,
)

logger = logging.getLogger(__name__)

_POSITIVE_DROPS = re.compile(r"^[1-9][0-9]*$")

ProviderPriceResolver = Callable[
    [ProviderRequestContext],
    str | int | Awaitable[str | int],
]


class ProviderPricingError(Exception):
    """A trusted provider price resolver rejected the purchase request."""

    def __init__(
        self,
        message: str,
        *,
        error: str = "invalid_request",
        status_code: int = 422,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.error = error
        self.status_code = status_code
        self.retryable = retryable


class ProviderPaymentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    protected_paths: str | Sequence[str]
    price_drops: str | None = Field(default=None, pattern=r"^[1-9][0-9]*$")
    pay_to_address: str
    facilitator_url: HttpUrl
    network: str = "xrpl:1"
    asset: str = "XRP"
    description: str = "SurplusFlow paid resource"
    max_timeout_seconds: int = Field(default=600, ge=1, le=3600)
    invoice_ttl_seconds: int = Field(default=900, ge=60, le=3600)
    source_tag: int = Field(default=20_260_530, ge=0, le=4_294_967_295)

    _validate_pay_to = field_validator("pay_to_address")(
        validate_classic_address
    )

    @field_validator("network")
    @classmethod
    def require_testnet(cls, value: str) -> str:
        if value != "xrpl:1":
            raise ValueError("SurplusFlow MVP providers must use xrpl:1")
        return value

    @field_validator("asset")
    @classmethod
    def require_xrp(cls, value: str) -> str:
        if value != "XRP":
            raise ValueError("SurplusFlow MVP providers must charge XRP")
        return value


def _path_set(paths: str | Sequence[str]) -> set[str]:
    return {paths} if isinstance(paths, str) else set(paths)


def _api_error(
    *,
    status_code: int,
    error: str,
    message: str,
    retryable: bool,
    request_id: str | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": error,
            "message": message,
            "retryable": retryable,
            "requestId": request_id or f"request_{uuid.uuid4().hex}",
        },
    )


def _normalize_price_drops(value: str | int) -> str:
    if isinstance(value, bool):
        raise ValueError("provider price must be a positive drops string or integer")
    normalized = str(value)
    if not _POSITIVE_DROPS.fullmatch(normalized):
        raise ValueError("provider price must be a positive drops string or integer")
    return normalized


async def _resolve_price(
    resolver: ProviderPriceResolver,
    context: ProviderRequestContext,
) -> str:
    resolved = resolver(context)
    if inspect.isawaitable(resolved):
        resolved = await resolved
    return _normalize_price_drops(resolved)


def _validate_purchase_intent_terms(
    context: ProviderRequestContext,
    config: ProviderPaymentConfig,
    expected_price_drops: str,
) -> JSONResponse | None:
    expected = {
        "amountDrops": expected_price_drops,
        "payTo": config.pay_to_address,
        "network": config.network,
        "asset": config.asset,
    }
    for field, expected_value in expected.items():
        actual_value = context.payload.get(field)
        if actual_value != expected_value:
            return _api_error(
                status_code=422,
                error="invalid_request",
                message=(
                    f"PurchaseIntent.{field} does not match the provider's "
                    "trusted payment terms"
                ),
                retryable=False,
                request_id=context.idempotency_key,
            )
    return None


def _decode_payment_payload(header_value: str) -> PaymentPayload | None:
    try:
        decoded = json.loads(base64.b64decode(header_value, validate=True))
        if not isinstance(decoded, dict):
            return None
        return PaymentPayload.from_dict(decoded)
    except Exception:  # The upstream x402 middleware returns the canonical error.
        return None


def _validate_signed_request_binding(
    header_value: str,
    *,
    context: ProviderRequestContext,
    config: ProviderPaymentConfig,
    expected_price_drops: str,
) -> JSONResponse | None:
    payment_payload = _decode_payment_payload(header_value)
    if payment_payload is None:
        return None

    accepted = payment_payload.accepted
    payload_invoice_id = payment_payload.payload.get("invoiceId")
    if (
        accepted.invoice_id() != context.invoice_id
        or payload_invoice_id != context.invoice_id
    ):
        return _api_error(
            status_code=409,
            error="invoice_mismatch",
            message="Signed payment invoice does not match this provider request",
            retryable=False,
            request_id=context.idempotency_key,
        )

    accepted_source_tag = (
        accepted.extra.get("sourceTag")
        if accepted.extra is not None
        else None
    )
    if (
        accepted.amount != expected_price_drops
        or accepted.pay_to != config.pay_to_address
        or accepted.network != config.network
        or accepted.asset != config.asset
        or accepted_source_tag != config.source_tag
    ):
        return _api_error(
            status_code=409,
            error="invoice_mismatch",
            message=(
                "Signed payment terms do not match the provider's current "
                "trusted payment terms"
            ),
            retryable=False,
            request_id=context.idempotency_key,
        )
    return None


def _build_x402_middleware(
    config: ProviderPaymentConfig,
    invoice_store: SQLiteInvoiceStore,
    *,
    price_drops: str,
    facilitator: Any | None,
):
    kwargs: dict[str, Any] = {
        "path": config.protected_paths,
        "price": price_drops,
        "pay_to_address": config.pay_to_address,
        "network": config.network,
        "asset": config.asset,
        "description": config.description,
        "max_timeout_seconds": config.max_timeout_seconds,
        "source_tag": config.source_tag,
        "invoice_store": invoice_store,
        "invoice_ttl_seconds": config.invoice_ttl_seconds,
        "invoice_id_factory": current_request_invoice_id,
    }
    if facilitator is None:
        kwargs["facilitator_url"] = str(config.facilitator_url)
    else:
        kwargs["facilitator"] = facilitator
    return require_payment(**kwargs)


def build_provider_middleware(
    config: ProviderPaymentConfig,
    invoice_store: SQLiteInvoiceStore,
    *,
    facilitator: Any | None = None,
    price_resolver: ProviderPriceResolver | None = None,
):
    """Build request-bound x402 middleware with fixed or trusted dynamic pricing.

    Prefer ``install_provider_payment`` so request fingerprinting, invoice
    binding, and paid-response replay are installed in the correct order.
    """

    if config.price_drops is None and price_resolver is None:
        raise ValueError("configure price_drops or provide price_resolver")
    if config.price_drops is not None and price_resolver is not None:
        raise ValueError("price_drops and price_resolver are mutually exclusive")

    protected_paths = _path_set(config.protected_paths)
    fixed_middleware = None
    dynamic_facilitator = facilitator
    if price_resolver is None:
        assert config.price_drops is not None
        fixed_middleware = _build_x402_middleware(
            config,
            invoice_store,
            price_drops=config.price_drops,
            facilitator=facilitator,
        )
    elif dynamic_facilitator is None:
        dynamic_facilitator = AsyncFacilitatorClient(
            FacilitatorClientOptions(base_url=str(config.facilitator_url))
        )

    async def middleware(request: Request, call_next) -> Response:
        if (
            request.method == "OPTIONS"
            or request.url.path not in protected_paths
        ):
            return await call_next(request)

        context = current_provider_request()
        if price_resolver is None:
            assert config.price_drops is not None
            expected_price_drops = config.price_drops
        else:
            try:
                expected_price_drops = await _resolve_price(
                    price_resolver,
                    context,
                )
            except ProviderPricingError as error:
                return _api_error(
                    status_code=error.status_code,
                    error=error.error,
                    message=str(error),
                    retryable=error.retryable,
                    request_id=context.idempotency_key,
                )
            except Exception:
                logger.exception("trusted provider price resolution failed")
                return _api_error(
                    status_code=500,
                    error="internal_error",
                    message="Provider could not calculate trusted payment terms",
                    retryable=True,
                    request_id=context.idempotency_key,
                )

            invalid_terms = _validate_purchase_intent_terms(
                context,
                config,
                expected_price_drops,
            )
            if invalid_terms is not None:
                return invalid_terms

        try:
            invoice_store.bind_request(
                context.invoice_id,
                context.fingerprint,
            )
        except InvoiceRequestConflictError:
            return _api_error(
                status_code=409,
                error="invoice_mismatch",
                message="Invoice ID was reused for a different provider request",
                retryable=False,
                request_id=context.idempotency_key,
            )

        payment_signature = request.headers.get("PAYMENT-SIGNATURE")
        if payment_signature:
            invalid_binding = _validate_signed_request_binding(
                payment_signature,
                context=context,
                config=config,
                expected_price_drops=expected_price_drops,
            )
            if invalid_binding is not None:
                return invalid_binding

        x402_middleware = fixed_middleware
        if x402_middleware is None:
            x402_middleware = _build_x402_middleware(
                config,
                invoice_store,
                price_drops=expected_price_drops,
                facilitator=dynamic_facilitator,
            )
        try:
            return await x402_middleware(request, call_next)
        except ValueError as error:
            if str(error) not in {
                "invoice id was reused with different payment requirements",
                "invoice has already been consumed",
            }:
                raise
            return _api_error(
                status_code=409,
                error="invoice_mismatch",
                message=str(error),
                retryable=False,
                request_id=context.idempotency_key,
            )

    return middleware


def install_provider_payment(
    app: FastAPI,
    config: ProviderPaymentConfig,
    invoice_store: SQLiteInvoiceStore,
    response_store: SQLiteProviderResponseStore,
    *,
    facilitator: Any | None = None,
    price_resolver: ProviderPriceResolver | None = None,
) -> None:
    """Install the complete provider boundary in the required middleware order."""

    app.middleware("http")(
        build_provider_middleware(
            config,
            invoice_store,
            facilitator=facilitator,
            price_resolver=price_resolver,
        )
    )
    app.add_middleware(
        ProviderIdempotencyMiddleware,
        store=response_store,
        protected_paths=config.protected_paths,
    )


def create_standalone_provider_app(
    config: ProviderPaymentConfig,
    invoice_store: SQLiteInvoiceStore,
    *,
    response_store: SQLiteProviderResponseStore | None = None,
    facilitator: Any | None = None,
    price_resolver: ProviderPriceResolver | None = None,
) -> FastAPI:
    """Minimal provider used before Person 3's services exist."""

    app = FastAPI(title="SurplusFlow standalone paid provider")
    install_provider_payment(
        app,
        config,
        invoice_store,
        response_store
        or SQLiteProviderResponseStore(
            invoice_store.path.with_name("provider-responses.sqlite3")
        ),
        facilitator=facilitator,
        price_resolver=price_resolver,
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/paid/demo", status_code=201)
    async def paid_demo() -> dict[str, str]:
        return {
            "reservationId": "reservation_standalone_001",
            "status": "confirmed",
            "valueDelivered": "exclusive demo food reservation",
        }

    return app
