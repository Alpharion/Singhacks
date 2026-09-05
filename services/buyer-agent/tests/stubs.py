"""Test doubles for the discovery boundary."""

from __future__ import annotations

from buyer_agent.models import DeliveryQuote, FoodOffer, ProcurementGoal


class StubDiscovery:
    """Returns exactly the offers and quotes a test hands it."""

    def __init__(self, offers: list[FoodOffer], quotes: list[DeliveryQuote]) -> None:
        self._offers = offers
        self._quotes = quotes
        self.offer_calls = 0
        self.quote_calls = 0

    async def list_offers(self, goal: ProcurementGoal) -> list[FoodOffer]:
        self.offer_calls += 1
        return list(self._offers)

    async def list_delivery_quotes(
        self, goal: ProcurementGoal, offers: list[FoodOffer], allocations: dict[str, int]
    ) -> list[DeliveryQuote]:
        self.quote_calls += 1
        return list(self._quotes)

    async def aclose(self) -> None:
        return None
