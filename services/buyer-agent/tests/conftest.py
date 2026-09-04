"""Shared test fixtures.

Every test loads the frozen contract fixtures from packages/contracts rather
than a local copy, so a contract change breaks these tests immediately.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from buyer_agent import timeutil
from buyer_agent.config import Settings, contracts_dir
from buyer_agent.models import (
    DeliveryQuote,
    DeliveryQuotesResponse,
    FoodOffer,
    FoodOffersResponse,
    ProcurementGoal,
)
from buyer_agent.policy import WalletPolicy

# The instant the frozen fixtures were written against.
DEMO_NOW = timeutil.parse("2026-09-05T06:00:00Z")


def fixture_path(name: str) -> Path:
    return contracts_dir() / "fixtures" / name


def load_fixture(name: str) -> dict:
    with open(fixture_path(name), encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture
def now() -> datetime:
    return DEMO_NOW


@pytest.fixture
def goal() -> ProcurementGoal:
    """The demo goal exactly as the frozen agent-run fixture states it."""
    return ProcurementGoal.model_validate(load_fixture("agent-run.json")["goal"])


@pytest.fixture
def offers() -> list[FoodOffer]:
    return list(FoodOffersResponse.model_validate(load_fixture("food-offers.json")).offers)


@pytest.fixture
def quotes() -> list[DeliveryQuote]:
    return list(
        DeliveryQuotesResponse.model_validate(load_fixture("delivery-quotes.json")).quotes
    )


@pytest.fixture
def settings() -> Settings:
    return Settings(
        discovery_mode="fixtures",
        payment_mode="simulated",
        openai_model="",
        openai_api_key="",
    )


@pytest.fixture
def policy(goal: ProcurementGoal, settings: Settings) -> WalletPolicy:
    from buyer_agent.policy import load_policy

    return load_policy(goal.wallet_policy_id, goal.max_total_spend_drops, settings)


def available(quote: DeliveryQuote) -> DeliveryQuote:
    """A copy of a quote with its demo unavailability lifted."""
    return quote.model_copy(update={"status": "available"})


def clock_from(start: datetime):
    """A monotonic fake clock so ordered timestamps stay ordered."""
    ticks = {"n": 0}

    def _now() -> datetime:
        ticks["n"] += 1
        return timeutil.plus(start, seconds=ticks["n"])

    return _now
