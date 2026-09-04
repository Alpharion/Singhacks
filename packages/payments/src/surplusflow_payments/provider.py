from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator
from x402_xrpl.server import require_payment

from .invoice_store import SQLiteInvoiceStore
from .models import validate_classic_address


class ProviderPaymentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    protected_paths: str | Sequence[str]
    price_drops: str = Field(pattern=r"^[1-9][0-9]*$")
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


def build_provider_middleware(
    config: ProviderPaymentConfig,
    invoice_store: SQLiteInvoiceStore,
    *,
    facilitator: Any | None = None,
):
    kwargs: dict[str, Any] = {
        "path": config.protected_paths,
        "price": config.price_drops,
        "pay_to_address": config.pay_to_address,
        "network": config.network,
        "asset": config.asset,
        "description": config.description,
        "max_timeout_seconds": config.max_timeout_seconds,
        "source_tag": config.source_tag,
        "invoice_store": invoice_store,
        "invoice_ttl_seconds": config.invoice_ttl_seconds,
    }
    if facilitator is None:
        kwargs["facilitator_url"] = str(config.facilitator_url)
    else:
        kwargs["facilitator"] = facilitator
    return require_payment(**kwargs)


def create_standalone_provider_app(
    config: ProviderPaymentConfig,
    invoice_store: SQLiteInvoiceStore,
    *,
    facilitator: Any | None = None,
) -> FastAPI:
    """Minimal provider used before Person 3's services exist."""

    app = FastAPI(title="SurplusFlow standalone paid provider")
    app.middleware("http")(
        build_provider_middleware(
            config,
            invoice_store,
            facilitator=facilitator,
        )
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/paid/demo")
    async def paid_demo() -> dict[str, str]:
        return {
            "reservationId": "reservation_standalone_001",
            "status": "confirmed",
            "valueDelivered": "exclusive demo food reservation",
        }

    return app
