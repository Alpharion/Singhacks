"""Provider discovery.

Discovery is free: no payment happens here. Two implementations share one
interface so the agent can be exercised end to end long before the marketplace
exists.

The fixture client rebases the frozen demo timestamps onto the run's real
deadline, keeping every interval (pickup windows, expiry, courier ETAs) exactly
as the contract froze them while letting the demo run on any day.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any, Protocol

import httpx

from . import config, timeutil
from .models import (
    DeliveryQuote,
    DeliveryQuoteRequest,
    DeliveryQuotesResponse,
    FoodOffer,
    FoodOffersResponse,
    Pickup,
    ProcurementGoal,
)

# The deadline the frozen fixtures were written against.
FIXTURE_DEADLINE = "2026-09-05T10:00:00Z"

_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")


class DiscoveryClient(Protocol):
    async def list_offers(self, goal: ProcurementGoal) -> list[FoodOffer]: ...

    async def list_delivery_quotes(
        self, goal: ProcurementGoal, offers: list[FoodOffer], allocations: dict[str, int]
    ) -> list[DeliveryQuote]: ...

    async def aclose(self) -> None: ...


def _shift(payload: Any, delta: timedelta) -> Any:
    if isinstance(payload, dict):
        return {key: _shift(value, delta) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_shift(item, delta) for item in payload]
    if isinstance(payload, str) and _TIMESTAMP.match(payload):
        return timeutil.iso(timeutil.parse(payload) + delta)
    return payload


class FixtureDiscoveryClient:
    """Serves the frozen contract fixtures. No marketplace required."""

    def __init__(self, fixtures_dir: str | None = None, *, rebase: bool = True) -> None:
        self._dir = fixtures_dir or str(config.contracts_dir() / "fixtures")
        self._rebase = rebase

    async def aclose(self) -> None:
        return None

    def _load(self, name: str, goal: ProcurementGoal) -> dict[str, Any]:
        with open(f"{self._dir}/{name}", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not self._rebase:
            return payload
        delta = timeutil.parse(goal.delivery_deadline) - timeutil.parse(FIXTURE_DEADLINE)
        return _shift(payload, delta)

    async def list_offers(self, goal: ProcurementGoal) -> list[FoodOffer]:
        payload = self._load("food-offers.json", goal)
        return list(FoodOffersResponse.model_validate(payload).offers)

    async def list_delivery_quotes(
        self, goal: ProcurementGoal, offers: list[FoodOffer], allocations: dict[str, int]
    ) -> list[DeliveryQuote]:
        payload = self._load("delivery-quotes.json", goal)
        return list(DeliveryQuotesResponse.model_validate(payload).quotes)


class HttpDiscoveryClient:
    """Talks to the marketplace service on port 8002."""

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self._client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def list_offers(self, goal: ProcurementGoal) -> list[FoodOffer]:
        # Deliberately does NOT send the marketplace's dietaryTag filter. The
        # agent's own hard filters are the authoritative dietary check, and
        # rejecting an incompatible offer here -- with a reason the buyer can
        # read -- is part of what the agent is for. Server-side pre-filtering
        # would silently hide those rejections from the decision record.
        params: dict[str, Any] = {"minQuantity": 1}
        response = await self._client.get("/api/offers", params=params)
        response.raise_for_status()
        return list(FoodOffersResponse.model_validate(response.json()).offers)

    async def list_delivery_quotes(
        self, goal: ProcurementGoal, offers: list[FoodOffer], allocations: dict[str, int]
    ) -> list[DeliveryQuote]:
        pickups = [
            Pickup(
                seller_id=offer.seller_id,
                offer_id=offer.offer_id,
                quantity=allocations.get(offer.offer_id, min(offer.quantity_available, goal.meal_count)),
                location=offer.location,
            )
            for offer in offers
        ]
        if not pickups:
            return []
        request = DeliveryQuoteRequest(
            goal_id=goal.goal_id,
            pickups=pickups,
            destination=goal.destination,
            delivery_deadline=goal.delivery_deadline,
        )
        response = await self._client.post("/api/delivery/quotes", json=request.wire())
        response.raise_for_status()
        return list(DeliveryQuotesResponse.model_validate(response.json()).quotes)


def build_discovery_client(settings: config.Settings) -> DiscoveryClient:
    if settings.discovery_mode == "http":
        return HttpDiscoveryClient(
            settings.marketplace_base_url, settings.request_timeout_seconds
        )
    if settings.discovery_mode == "fixtures":
        return FixtureDiscoveryClient()
    raise RuntimeError(f"unknown BUYER_AGENT_DISCOVERY_MODE: {settings.discovery_mode}")
