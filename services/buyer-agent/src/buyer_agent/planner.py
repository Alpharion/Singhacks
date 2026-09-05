"""The deterministic optimizer.

One seller rarely covers a whole order, so the planner enumerates combinations
of eligible offers, allocates portions under several strategies, pairs each
bundle with a courier that can actually collect from every seller in it, and
ranks the results. No language model participates: given the same inputs this
returns the same plan every time, which is what makes the spend auditable.

With three sellers the subset space is trivial, so ``itertools`` is enough and
no optimization framework is warranted.
"""

from __future__ import annotations

import hashlib
import itertools
from dataclasses import dataclass
from datetime import datetime

from . import drops, timeutil
from .models import (
    DeliveryQuote,
    FoodAllocation,
    FoodOffer,
    OptimizationPriority,
    ProcurementGoal,
    ProcurementPlan,
)

# Risk weights. Reliability dominates, then how close the food is to expiry,
# then how little slack is left before the delivery deadline.
RELIABILITY_WEIGHT = 60.0
EXPIRY_WEIGHT = 25.0
DEADLINE_WEIGHT = 15.0
EXPIRY_COMFORT_HOURS = 6.0
DEADLINE_COMFORT_MINUTES = 60.0

ALLOCATION_STRATEGIES = ("cost_first", "reliability_first", "waste_first", "even_split")


@dataclass(frozen=True)
class Bundle:
    allocations: tuple[FoodAllocation, ...]
    seller_ids: frozenset[str]
    meals: int
    food_cost_drops: int
    min_expiry_hours: float
    weighted_reliability: float


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _allocate(
    offers: list[FoodOffer], needed: int, strategy: str, now: datetime
) -> tuple[FoodAllocation, ...] | None:
    """Split ``needed`` meals across a fixed set of offers under one strategy."""
    if strategy == "even_split":
        capacity = sum(offer.quantity_available for offer in offers)
        if capacity == 0:
            return None
        quantities: dict[str, int] = {}
        for offer in offers:
            share = min(
                offer.quantity_available,
                needed * offer.quantity_available // capacity,
            )
            quantities[offer.offer_id] = share
        # Hand the rounding remainder to the cheapest offers with room left.
        for offer in sorted(offers, key=lambda item: drops.to_int(item.unit_price_drops)):
            if sum(quantities.values()) >= needed:
                break
            headroom = offer.quantity_available - quantities[offer.offer_id]
            take = min(headroom, needed - sum(quantities.values()))
            quantities[offer.offer_id] += take
        ordered = offers
    else:
        if strategy == "cost_first":
            ordered = sorted(offers, key=lambda item: drops.to_int(item.unit_price_drops))
        elif strategy == "reliability_first":
            ordered = sorted(offers, key=lambda item: -item.reliability_score)
        else:  # waste_first: rescue whatever expires soonest
            ordered = sorted(offers, key=lambda item: timeutil.parse(item.expires_at))
        quantities = {}
        remaining = needed
        for offer in ordered:
            take = min(offer.quantity_available, remaining)
            quantities[offer.offer_id] = take
            remaining -= take

    allocations = []
    for offer in ordered:
        quantity = quantities.get(offer.offer_id, 0)
        if quantity <= 0:
            continue
        unit = drops.to_int(offer.unit_price_drops)
        allocations.append(
            FoodAllocation(
                seller_id=offer.seller_id,
                offer_id=offer.offer_id,
                quantity=quantity,
                unit_price_drops=offer.unit_price_drops,
                line_total_drops=drops.to_str(unit * quantity),
                reliability_score=offer.reliability_score,
            )
        )
    if not allocations:
        return None
    return tuple(allocations)


def build_bundles(offers: list[FoodOffer], needed: int, now: datetime) -> list[Bundle]:
    """Every distinct way to source up to ``needed`` meals from these offers."""
    by_id = {offer.offer_id: offer for offer in offers}
    seen: set[tuple[tuple[str, int], ...]] = set()
    bundles: list[Bundle] = []

    for size in range(1, len(offers) + 1):
        for subset in itertools.combinations(offers, size):
            for strategy in ALLOCATION_STRATEGIES:
                allocations = _allocate(list(subset), needed, strategy, now)
                if allocations is None:
                    continue
                signature = tuple(
                    sorted((item.offer_id, item.quantity) for item in allocations)
                )
                if signature in seen:
                    continue
                seen.add(signature)

                meals = sum(item.quantity for item in allocations)
                food_cost = drops.total(item.line_total_drops for item in allocations)
                weighted = (
                    sum(item.reliability_score * item.quantity for item in allocations) / meals
                )
                min_expiry = min(
                    timeutil.hours_between(now, timeutil.parse(by_id[item.offer_id].expires_at))
                    for item in allocations
                )
                bundles.append(
                    Bundle(
                        allocations=allocations,
                        seller_ids=frozenset(item.seller_id for item in allocations),
                        meals=meals,
                        food_cost_drops=food_cost,
                        min_expiry_hours=min_expiry,
                        weighted_reliability=weighted,
                    )
                )
    return bundles


def _risk_score(
    bundle: Bundle, quote: DeliveryQuote, goal: ProcurementGoal, now: datetime
) -> float:
    reliability = 0.7 * bundle.weighted_reliability + 0.3 * quote.reliability_score
    reliability_risk = (1.0 - reliability) * RELIABILITY_WEIGHT

    expiry_risk = EXPIRY_WEIGHT * (
        1.0 - _clamp(bundle.min_expiry_hours / EXPIRY_COMFORT_HOURS)
    )

    slack = timeutil.minutes_between(
        timeutil.parse(quote.delivery_eta), timeutil.parse(goal.delivery_deadline)
    )
    deadline_risk = DEADLINE_WEIGHT * (1.0 - _clamp(slack / DEADLINE_COMFORT_MINUTES))

    return round(reliability_risk + expiry_risk + deadline_risk, 1)


def _plan_id(bundle: Bundle, quote: DeliveryQuote) -> str:
    """Stable across replans so the UI can follow a plan between rounds."""
    signature = "|".join(
        [quote.quote_id]
        + sorted(f"{item.offer_id}:{item.quantity}" for item in bundle.allocations)
    )
    return "plan_" + hashlib.sha256(signature.encode()).hexdigest()[:12]


def build_plans(
    goal: ProcurementGoal,
    offers: list[FoodOffer],
    quotes: list[DeliveryQuote],
    now: datetime,
    *,
    meals_needed: int | None = None,
    budget_drops: int | None = None,
    committed_seller_ids: frozenset[str] = frozenset(),
) -> list[ProcurementPlan]:
    """Build and rank plans.

    ``meals_needed`` and ``budget_drops`` shrink after a partial fulfilment, and
    ``committed_seller_ids`` are sellers already paid, whose pickups the courier
    must still be able to cover.
    """
    needed = meals_needed if meals_needed is not None else goal.meal_count
    budget = (
        budget_drops
        if budget_drops is not None
        else drops.to_int(goal.max_total_spend_drops)
    )
    plans: list[ProcurementPlan] = []

    for bundle in build_bundles(offers, needed, now):
        required_pickups = bundle.seller_ids | committed_seller_ids
        for quote in quotes:
            if not required_pickups <= set(quote.pickup_seller_ids):
                continue

            delivery_cost = drops.to_int(quote.price_drops)
            total_cost = bundle.food_cost_drops + delivery_cost

            reasons: list[str] = []
            if bundle.meals < needed:
                reasons.append(
                    f"Covers only {bundle.meals} of the {needed} meals still required."
                )
            if total_cost > budget:
                reasons.append(
                    f"Total {drops.to_xrp_label(total_cost)} exceeds the remaining "
                    f"{drops.to_xrp_label(budget)} budget."
                )
            if quote.capacity_meals < bundle.meals:
                reasons.append(
                    f"{quote.provider_name} cannot carry {bundle.meals} meals."
                )

            valid_until = min(
                timeutil.parse(quote.valid_until),
                min(
                    timeutil.parse(offer.expires_at)
                    for offer in offers
                    if offer.offer_id in {item.offer_id for item in bundle.allocations}
                ),
            )

            plans.append(
                ProcurementPlan(
                    plan_id=_plan_id(bundle, quote),
                    goal_id=goal.goal_id,
                    food_allocations=list(bundle.allocations),
                    delivery_quote_id=quote.quote_id,
                    total_meals=bundle.meals,
                    food_cost_drops=drops.to_str(bundle.food_cost_drops),
                    delivery_cost_drops=drops.to_str(delivery_cost),
                    total_cost_drops=drops.to_str(total_cost),
                    expected_delivery_at=quote.delivery_eta,
                    valid_until=timeutil.iso(valid_until),
                    risk_score=_risk_score(bundle, quote, goal, now),
                    feasible=not reasons,
                    rejection_reasons=reasons,
                )
            )

    return rank(plans, goal, budget)


def _score(plan: ProcurementPlan, priority: OptimizationPriority, budget: int) -> tuple:
    cost = drops.to_int(plan.total_cost_drops)
    if priority == "lowest_cost":
        return (cost, plan.risk_score, plan.plan_id)
    if priority == "highest_reliability":
        return (plan.risk_score, cost, plan.plan_id)
    if priority == "lowest_waste":
        # Prefer the plan that rescues the most portions, then the cheapest.
        return (-plan.total_meals, cost, plan.plan_id)
    blended = 0.7 * (cost / budget) + 0.3 * (plan.risk_score / 100.0)
    return (round(blended, 6), cost, plan.plan_id)


def rank(
    plans: list[ProcurementPlan], goal: ProcurementGoal, budget: int
) -> list[ProcurementPlan]:
    """Feasible plans first, each group ordered by the buyer's stated priority."""
    return sorted(
        plans,
        key=lambda plan: (
            not plan.feasible,
            _score(plan, goal.optimization_priority, budget),
        ),
    )
