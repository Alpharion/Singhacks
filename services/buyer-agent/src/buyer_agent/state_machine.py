"""The procurement state machine.

An explicit loop rather than an agent framework: discover, filter, plan, select,
authorize, pay, confirm, and replan on failure. Every transition appends an
event and, where money or a provider choice is involved, an auditable
AgentDecision. The language model contributes phrasing; it never selects a
provider, sets an amount, or approves a payment.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from . import drops, ids, intents, timeutil
from .config import Settings
from .discovery import DiscoveryClient
from .filtering import Rejection, filter_offers, filter_quotes
from .llm import explain_selection
from .models import (
    AgentDecision,
    AgentRun,
    ApiError,
    DecisionType,
    DeliveryBooking,
    DeliveryQuote,
    ErrorCode,
    EventType,
    FoodOffer,
    ProcurementGoal,
    ProcurementPlan,
    RejectedAlternative,
    Reservation,
    RunEvent,
    RunStatus,
    Spend,
)
from .payments import PaymentClient, Recovery
from .planner import build_plans
from .policy import WalletPolicy

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PurchaseFailure:
    """Why a purchase failed, and what the run may safely do next."""

    option_id: str
    recovery: Recovery
    error: ApiError | None = None

    @property
    def message(self) -> str:
        return self.error.message if self.error else f"{self.option_id} could not be purchased."


@dataclass
class RunState:
    """Mutable working state that snapshots into the frozen AgentRun contract."""

    run_id: str
    goal: ProcurementGoal
    policy: WalletPolicy
    created_at: str
    updated_at: str
    status: RunStatus = "queued"
    offers: list[FoodOffer] = field(default_factory=list)
    delivery_quotes: list[DeliveryQuote] = field(default_factory=list)
    plans: list[ProcurementPlan] = field(default_factory=list)
    selected_plan_id: str | None = None
    decisions: list[AgentDecision] = field(default_factory=list)
    reservations: list[Reservation] = field(default_factory=list)
    delivery_bookings: list[DeliveryBooking] = field(default_factory=list)
    events: list[RunEvent] = field(default_factory=list)
    failure: ApiError | None = None
    food_spent_drops: int = 0
    delivery_spent_drops: int = 0
    _sequence: int = 0

    @property
    def total_spent_drops(self) -> int:
        return self.food_spent_drops + self.delivery_spent_drops

    @property
    def remaining_drops(self) -> int:
        return max(0, self.policy.max_order_spend_drops - self.total_spent_drops)

    @property
    def secured_meals(self) -> int:
        return sum(item.quantity for item in self.reservations)

    @property
    def secured_offer_ids(self) -> frozenset[str]:
        return frozenset(item.offer_id for item in self.reservations)

    @property
    def committed_seller_ids(self) -> frozenset[str]:
        return frozenset(item.seller_id for item in self.reservations)

    @property
    def objective(self) -> str:
        tags = ", ".join(tag.replace("_", " ") for tag in self.goal.dietary_tags)
        return (
            f"Acquire {self.goal.meal_count} {tags} meals delivered to "
            f"{self.goal.destination.zone} by {self.goal.delivery_deadline} for at most "
            f"{drops.to_xrp_label(self.goal.max_total_spend_drops)}."
        )

    def touch(self, at: datetime) -> None:
        self.updated_at = timeutil.iso(at)

    def event(
        self, event_type: EventType, message: str, at: datetime, related_id: str | None = None
    ) -> None:
        self._sequence += 1
        self.events.append(
            RunEvent(
                sequence=self._sequence,
                event_type=event_type,
                message=message,
                related_id=related_id,
                created_at=timeutil.iso(at),
            )
        )
        self.touch(at)

    def decide(
        self,
        decision_type: DecisionType,
        *,
        at: datetime,
        reasons: list[str],
        alternatives: list[str],
        selected: str | None = None,
        rejected: list[RejectedAlternative] | None = None,
        transaction_hash: str | None = None,
    ) -> None:
        self.decisions.append(
            AgentDecision(
                decision_id=ids.unique("decision"),
                run_id=self.run_id,
                decision_type=decision_type,
                objective=self.objective,
                selected_option_id=selected,
                alternatives_considered=alternatives,
                reasons=reasons,
                rejected_alternatives=rejected or [],
                remaining_budget_drops=drops.to_str(self.remaining_drops),
                wallet_policy_id=self.policy.wallet_policy_id,
                transaction_hash=transaction_hash,
                created_at=timeutil.iso(at),
            )
        )
        self.touch(at)

    def add_plans(self, plans: list[ProcurementPlan]) -> None:
        """Accumulate every plan considered so the buyer can see the alternatives."""
        known = {plan.plan_id for plan in self.plans}
        self.plans = [plan for plan in plans if plan.plan_id not in known] + [
            plan for plan in self.plans if plan.plan_id in known
        ]

    def fail(self, error: ErrorCode, message: str, at: datetime, retryable: bool = False) -> None:
        self.status = "failed"
        self.failure = ApiError(
            error=error,
            message=message,
            retryable=retryable,
            request_id=ids.unique("request"),
        )
        self.event("run_failed", message, at)

    def snapshot(self) -> AgentRun:
        return AgentRun(
            run_id=self.run_id,
            status=self.status,
            goal=self.goal,
            offers=list(self.offers),
            delivery_quotes=list(self.delivery_quotes),
            plans=list(self.plans),
            selected_plan_id=self.selected_plan_id,
            decisions=list(self.decisions),
            reservations=list(self.reservations),
            delivery_bookings=list(self.delivery_bookings),
            spend=Spend(
                food_drops=drops.to_str(self.food_spent_drops),
                delivery_drops=drops.to_str(self.delivery_spent_drops),
                total_drops=drops.to_str(self.total_spent_drops),
                remaining_drops=drops.to_str(self.remaining_drops),
            ),
            events=list(self.events),
            failure=self.failure,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class ProcurementAgent:
    """Drives one run to fulfilment or to an explained failure."""

    def __init__(
        self,
        *,
        discovery: DiscoveryClient,
        payments: PaymentClient,
        settings: Settings,
        clock: Callable[[], datetime] | None = None,
        on_update: Callable[[RunState], None] | None = None,
    ) -> None:
        self._discovery = discovery
        self._payments = payments
        self._settings = settings
        self._clock = clock or timeutil.now
        self._on_update = on_update

    def _publish(self, state: RunState) -> None:
        if self._on_update is not None:
            self._on_update(state)

    async def execute(self, state: RunState) -> RunState:
        try:
            await self._execute(state)
        except Exception as exc:  # noqa: BLE001 - a run must always end explainably
            log.exception("run %s failed", state.run_id)
            state.fail("internal_error", f"The run stopped unexpectedly: {exc}", self._clock())
        self._publish(state)
        return state

    # ------------------------------------------------------------------ phases

    async def _execute(self, state: RunState) -> None:
        now = self._clock()
        goal = state.goal

        state.status = "discovering"
        self._publish(state)

        offers = await self._discovery.list_offers(goal)
        state.offers = offers
        state.event(
            "offers_discovered",
            f"Discovered {len(offers)} food offers from "
            f"{len({offer.seller_id for offer in offers})} sellers.",
            now,
        )

        eligible_offers, offer_rejections = filter_offers(goal, offers, now)

        quotes = await self._discovery.list_delivery_quotes(goal, eligible_offers, {})
        state.delivery_quotes = quotes
        eligible_quotes, quote_rejections = filter_quotes(
            goal, quotes, now, meals_required=goal.meal_count
        )

        for rejection in offer_rejections:
            state.event(
                "offer_rejected", " ".join(rejection.reasons), now, related_id=rejection.option_id
            )
        for rejection in quote_rejections:
            state.event(
                "provider_failed", " ".join(rejection.reasons), now, related_id=rejection.option_id
            )

        all_rejections = offer_rejections + quote_rejections
        if all_rejections:
            state.decide(
                "reject_offer",
                at=now,
                reasons=[
                    f"{len(all_rejections)} of {len(offers) + len(quotes)} discovered options "
                    "failed a hard dietary, expiry, capacity, reliability, or authorization rule."
                ],
                alternatives=[offer.offer_id for offer in offers]
                + [quote.quote_id for quote in quotes],
                rejected=[
                    RejectedAlternative(option_id=item.option_id, reasons=item.reasons)
                    for item in all_rejections
                ],
            )
        self._publish(state)

        if not eligible_offers:
            state.fail(
                "offer_sold_out",
                "No discovered offer satisfies the dietary, expiry, reliability, and "
                "authorization rules for this request.",
                now,
            )
            return
        if not eligible_quotes:
            state.fail(
                "provider_unavailable",
                "No courier can collect from the eligible sellers and arrive before the deadline.",
                now,
            )
            return

        await self._procure(state, eligible_offers, eligible_quotes)

    async def _procure(
        self, state: RunState, offers: list[FoodOffer], quotes: list[DeliveryQuote]
    ) -> None:
        available_offers = list(offers)
        available_quotes = list(quotes)
        attempts = 0
        preferred_quote_id: str | None = None

        while True:
            now = self._clock()
            remaining_meals = state.goal.meal_count - state.secured_meals

            if remaining_meals > 0:
                state.status = "planning"
                self._publish(state)

                plans = build_plans(
                    state.goal,
                    [offer for offer in available_offers if offer.offer_id not in state.secured_offer_ids],
                    available_quotes,
                    now,
                    meals_needed=remaining_meals,
                    budget_drops=state.remaining_drops,
                    committed_seller_ids=state.committed_seller_ids,
                )
                state.add_plans(plans)
                state.event(
                    "plans_built",
                    f"Built {len(plans)} candidate plans for {remaining_meals} meals; "
                    f"{sum(1 for plan in plans if plan.feasible)} are feasible within "
                    f"{drops.to_xrp_label(state.remaining_drops)}.",
                    now,
                )

                feasible = [plan for plan in plans if plan.feasible]
                if not feasible:
                    self._stop_without_plan(state, plans, now)
                    return

                plan = feasible[0]
                preferred_quote_id = plan.delivery_quote_id
                state.selected_plan_id = plan.plan_id
                self._record_selection(state, plan, feasible, now)
                self._publish(state)

                failure = await self._secure_food(state, plan, available_offers)
                if failure is not None:
                    if failure.recovery is Recovery.HALT:
                        self._halt(state, failure)
                        return
                    attempts += 1
                    available_offers = [
                        offer
                        for offer in available_offers
                        if offer.offer_id != failure.option_id
                    ]
                    if attempts > self._settings.max_replans:
                        state.fail(
                            "provider_unavailable",
                            "Too many providers failed in a row; stopping before spending more.",
                            self._clock(),
                        )
                        return
                    self._record_replan(state, failure.option_id, self._clock())
                    self._publish(state)
                    continue

            now = self._clock()
            quote = self._select_delivery(state, available_quotes, preferred_quote_id, now)
            if quote is None:
                state.fail(
                    "provider_unavailable",
                    "No remaining courier can collect from every reserved seller within budget "
                    "and before the deadline.",
                    now,
                )
                return

            failure = await self._book_delivery(state, quote)
            if failure is not None:
                if failure.recovery is Recovery.HALT:
                    self._halt(state, failure)
                    return
                attempts += 1
                available_quotes = [
                    item for item in available_quotes if item.quote_id != quote.quote_id
                ]
                preferred_quote_id = None
                if attempts > self._settings.max_replans:
                    state.fail(
                        "provider_unavailable",
                        "Too many couriers failed in a row; stopping before spending more.",
                        self._clock(),
                    )
                    return
                self._record_replan(state, quote.quote_id, self._clock())
                self._publish(state)
                continue

            break

        now = self._clock()
        state.status = "fulfilled"
        state.event(
            "run_fulfilled",
            f"{state.secured_meals} meals and delivery confirmed for "
            f"{drops.to_xrp_label(state.total_spent_drops)}, "
            f"{drops.to_xrp_label(state.remaining_drops)} of budget unspent.",
            now,
            related_id=state.selected_plan_id,
        )
        state.decide(
            "stop",
            at=now,
            reasons=[
                f"The requested {state.goal.meal_count} meals are reserved and a courier is booked.",
                f"Total spend {drops.to_xrp_label(state.total_spent_drops)} stayed within the "
                f"{drops.to_xrp_label(state.policy.max_order_spend_drops)} delegated budget.",
            ],
            alternatives=[],
            selected=state.selected_plan_id,
        )

    # ----------------------------------------------------------------- helpers

    def _halt(self, state: RunState, failure: PurchaseFailure) -> None:
        """Stop the run without another payment attempt.

        Reached when a payment may already be in flight or settled. Replanning
        here could pay a second time for the same resource, so the run ends and
        the stored transaction hash is left for reconciliation.
        """
        now = self._clock()
        state.decide(
            "stop",
            at=now,
            reasons=[
                failure.message,
                "Stopping instead of replanning: another attempt could pay twice for the "
                "same resource.",
                f"{drops.to_xrp_label(state.total_spent_drops)} has settled so far across "
                f"{len(state.reservations)} reservations.",
            ],
            alternatives=[failure.option_id],
            selected=None,
        )
        error = failure.error
        state.fail(
            error.error if error else "payment_failed",
            failure.message,
            now,
            retryable=False,
        )
        self._publish(state)

    def _stop_without_plan(
        self, state: RunState, plans: list[ProcurementPlan], now: datetime
    ) -> None:
        rejected = [
            RejectedAlternative(option_id=plan.plan_id, reasons=plan.rejection_reasons)
            for plan in plans
            if plan.rejection_reasons
        ][:10]
        state.decide(
            "stop",
            at=now,
            reasons=[
                "No remaining combination of sellers and couriers can deliver the outstanding "
                f"{state.goal.meal_count - state.secured_meals} meals within "
                f"{drops.to_xrp_label(state.remaining_drops)}."
            ],
            alternatives=[plan.plan_id for plan in plans],
            rejected=rejected,
        )
        state.fail(
            "budget_exceeded" if plans else "offer_sold_out",
            "No feasible plan remains for the outstanding meals within the delegated budget.",
            now,
        )

    def _record_selection(
        self,
        state: RunState,
        plan: ProcurementPlan,
        feasible: list[ProcurementPlan],
        now: datetime,
    ) -> None:
        sellers = ", ".join(
            f"{item.quantity} from {item.seller_id}" for item in plan.food_allocations
        )
        reasons = [
            f"Sources {plan.total_meals} meals as {sellers}.",
            f"Total {drops.to_xrp_label(plan.total_cost_drops)} "
            f"({drops.to_xrp_label(plan.food_cost_drops)} food, "
            f"{drops.to_xrp_label(plan.delivery_cost_drops)} delivery) fits the remaining "
            f"{drops.to_xrp_label(state.remaining_drops)}.",
            f"Arrives {plan.expected_delivery_at}, before the {state.goal.delivery_deadline} deadline.",
            f"Ranked first on the buyer's '{state.goal.optimization_priority}' priority "
            f"with a risk score of {plan.risk_score}.",
        ]

        runners_up = [item for item in feasible if item.plan_id != plan.plan_id][:3]
        rejected = [
            RejectedAlternative(
                option_id=item.plan_id,
                reasons=[
                    f"Costs {drops.to_xrp_label(item.total_cost_drops)} against "
                    f"{drops.to_xrp_label(plan.total_cost_drops)} for the selected plan "
                    f"(risk {item.risk_score} vs {plan.risk_score})."
                ],
            )
            for item in runners_up
        ]

        sentence = explain_selection(
            "Objective: "
            + state.objective
            + "\nChosen plan: "
            + f"{plan.total_meals} meals, {drops.to_xrp_label(plan.total_cost_drops)} total, "
            + f"risk {plan.risk_score}, arriving {plan.expected_delivery_at}."
            + "\nAlternatives: "
            + "; ".join(
                f"{item.total_meals} meals for {drops.to_xrp_label(item.total_cost_drops)}, "
                f"risk {item.risk_score}"
                for item in runners_up
            ),
            self._settings,
        )
        if sentence:
            reasons.append(sentence)

        state.decide(
            "select_plan",
            at=now,
            reasons=reasons,
            alternatives=[item.plan_id for item in feasible],
            selected=plan.plan_id,
            rejected=rejected,
        )
        state.event(
            "plan_selected",
            f"Selected {plan.plan_id}: {plan.total_meals} meals for "
            f"{drops.to_xrp_label(plan.total_cost_drops)} arriving {plan.expected_delivery_at}.",
            now,
            related_id=plan.plan_id,
        )

    def _record_replan(self, state: RunState, failed_id: str, now: datetime) -> None:
        state.status = "replanning"
        state.event(
            "replanning_started",
            f"Rebuilding the plan without {failed_id}; "
            f"{state.goal.meal_count - state.secured_meals} meals still outstanding and "
            f"{drops.to_xrp_label(state.remaining_drops)} of budget left.",
            now,
            related_id=failed_id,
        )
        state.decide(
            "replan",
            at=now,
            reasons=[
                f"{failed_id} became unavailable, so the remaining requirement is re-planned "
                "against the providers that are still valid."
            ],
            alternatives=[failed_id],
            rejected=[
                RejectedAlternative(
                    option_id=failed_id, reasons=["Provider could not fulfil the request."]
                )
            ],
        )

    def _select_delivery(
        self,
        state: RunState,
        quotes: list[DeliveryQuote],
        preferred_quote_id: str | None,
        now: datetime,
    ) -> DeliveryQuote | None:
        """Choose a courier that can collect from every seller already paid."""
        if any(booking.status != "failed" for booking in state.delivery_bookings):
            return None

        required = state.committed_seller_ids
        meals = state.secured_meals
        candidates = [
            quote
            for quote in quotes
            if required <= set(quote.pickup_seller_ids)
            and quote.capacity_meals >= meals
            and drops.to_int(quote.price_drops) <= state.remaining_drops
            and timeutil.parse(quote.delivery_eta) <= timeutil.parse(state.goal.delivery_deadline)
            and timeutil.parse(quote.valid_until) > now
        ]
        if not candidates:
            return None
        for quote in candidates:
            if quote.quote_id == preferred_quote_id:
                return quote
        return sorted(
            candidates,
            key=lambda quote: (
                drops.to_int(quote.price_drops),
                -quote.reliability_score,
                quote.quote_id,
            ),
        )[0]

    async def _secure_food(
        self, state: RunState, plan: ProcurementPlan, offers: list[FoodOffer]
    ) -> PurchaseFailure | None:
        """Pay for each allocation. Returns the first failure, if any."""
        by_id = {offer.offer_id: offer for offer in offers}
        delivery_reserve = drops.to_int(plan.delivery_cost_drops)

        for allocation in plan.food_allocations:
            if allocation.offer_id in state.secured_offer_ids:
                continue
            offer = by_id.get(allocation.offer_id)
            if offer is None:
                return PurchaseFailure(allocation.offer_id, Recovery.REPLAN)

            now = self._clock()
            state.status = "awaiting_payment"
            amount = drops.to_int(allocation.line_total_drops)

            state.event(
                "payment_required",
                f"{offer.seller_name} requires {drops.to_xrp_label(amount)} to reserve "
                f"{allocation.quantity} meals.",
                now,
                related_id=offer.offer_id,
            )

            rejection = self._authorize(state, amount, offer.pay_to, delivery_reserve)
            if rejection is not None:
                state.event("provider_failed", rejection, now, related_id=offer.offer_id)
                state.decide(
                    "replan",
                    at=now,
                    reasons=[rejection],
                    alternatives=[offer.offer_id],
                    rejected=[
                        RejectedAlternative(option_id=offer.offer_id, reasons=[rejection])
                    ],
                )
                return PurchaseFailure(offer.offer_id, Recovery.REPLAN)

            intent = intents.food_intent(
                run_id=state.run_id,
                goal=state.goal,
                offer=offer,
                allocation=allocation,
                policy=state.policy,
                rationale=(
                    f"Supplies {allocation.quantity} compatible meals at "
                    f"{drops.to_xrp_label(allocation.unit_price_drops)} each and keeps the "
                    f"plan within the {drops.to_xrp_label(state.policy.max_order_spend_drops)} budget."
                ),
                now=now,
            )
            state.event(
                "payment_authorized",
                f"Authorized {intents.describe(intent)} under wallet policy "
                f"{state.policy.wallet_policy_id}.",
                now,
                related_id=offer.offer_id,
            )
            self._publish(state)

            state.status = "reserving"
            outcome = await self._payments.purchase(
                intent,
                offer=offer,
                already_spent_drops=state.total_spent_drops,
                now=now,
            )
            now = self._clock()

            if not outcome.ok or outcome.reservation is None or outcome.receipt is None:
                failure = PurchaseFailure(offer.offer_id, outcome.recovery, outcome.error)
                state.event(
                    "provider_failed",
                    outcome.error.message
                    if outcome.error
                    else f"{offer.seller_name} did not return a reservation.",
                    now,
                    related_id=offer.offer_id,
                )
                return failure

            state.food_spent_drops += drops.to_int(outcome.receipt.amount_drops)
            state.reservations.append(outcome.reservation)
            state.event(
                "payment_settled",
                self._settlement_message(outcome.receipt.transaction, outcome.simulated),
                now,
                related_id=offer.offer_id,
            )
            state.decide(
                "authorize_payment",
                at=now,
                reasons=[
                    f"Paid {drops.to_xrp_label(outcome.receipt.amount_drops)} to "
                    f"{offer.seller_name} for {allocation.quantity} meals.",
                    f"Amount, recipient, and invoice matched the authorized intent "
                    f"{intent.intent_id}.",
                ],
                alternatives=[offer.offer_id],
                selected=offer.offer_id,
                transaction_hash=outcome.receipt.transaction,
            )
            state.event(
                "reservation_confirmed",
                f"Reservation {outcome.reservation.reservation_id} confirmed for "
                f"{allocation.quantity} meals from {offer.seller_name}.",
                now,
                related_id=outcome.reservation.reservation_id,
            )
            self._publish(state)

        return None

    async def _book_delivery(
        self, state: RunState, quote: DeliveryQuote
    ) -> PurchaseFailure | None:
        now = self._clock()
        state.status = "awaiting_payment"
        amount = drops.to_int(quote.price_drops)

        state.event(
            "payment_required",
            f"{quote.provider_name} requires {drops.to_xrp_label(amount)} to confirm delivery.",
            now,
            related_id=quote.quote_id,
        )

        rejection = self._authorize(state, amount, quote.pay_to, 0)
        if rejection is not None:
            state.event("provider_failed", rejection, now, related_id=quote.quote_id)
            return PurchaseFailure(quote.quote_id, Recovery.REPLAN)

        intent = intents.delivery_intent(
            run_id=state.run_id,
            goal=state.goal,
            quote=quote,
            policy=state.policy,
            rationale=(
                f"Collects from every reserved seller and arrives {quote.delivery_eta}, "
                f"before the {state.goal.delivery_deadline} deadline."
            ),
            now=now,
        )
        state.event(
            "payment_authorized",
            f"Authorized {intents.describe(intent)} under wallet policy "
            f"{state.policy.wallet_policy_id}.",
            now,
            related_id=quote.quote_id,
        )
        self._publish(state)

        outcome = await self._payments.purchase(
            intent,
            quote=quote,
            already_spent_drops=state.total_spent_drops,
            now=now,
        )
        now = self._clock()

        if not outcome.ok or outcome.booking is None or outcome.receipt is None:
            state.event(
                "provider_failed",
                outcome.error.message
                if outcome.error
                else f"{quote.provider_name} did not return a booking.",
                now,
                related_id=quote.quote_id,
            )
            return PurchaseFailure(quote.quote_id, outcome.recovery, outcome.error)

        state.delivery_spent_drops += drops.to_int(outcome.receipt.amount_drops)
        state.delivery_bookings.append(outcome.booking)
        state.event(
            "payment_settled",
            self._settlement_message(outcome.receipt.transaction, outcome.simulated),
            now,
            related_id=quote.quote_id,
        )
        state.decide(
            "authorize_payment",
            at=now,
            reasons=[
                f"Paid {drops.to_xrp_label(outcome.receipt.amount_drops)} to "
                f"{quote.provider_name} for delivery to {state.goal.destination.zone}.",
                f"Amount, recipient, and invoice matched the authorized intent {intent.intent_id}.",
            ],
            alternatives=[quote.quote_id],
            selected=quote.quote_id,
            transaction_hash=outcome.receipt.transaction,
        )
        state.event(
            "delivery_confirmed",
            f"Booking {outcome.booking.booking_id} confirmed, arriving "
            f"{outcome.booking.delivery_eta}.",
            now,
            related_id=outcome.booking.booking_id,
        )
        self._publish(state)
        return None

    def _authorize(
        self, state: RunState, amount: int, pay_to: str, reserve: int
    ) -> str | None:
        from .policy import authorize

        rejection = authorize(
            state.policy,
            amount_drops=amount,
            pay_to=pay_to,
            already_spent_drops=state.total_spent_drops,
            reserve_drops=reserve,
        )
        return rejection.reason if rejection else None

    @staticmethod
    def _settlement_message(transaction: str, simulated: bool) -> str:
        if simulated:
            return (
                "Simulated settlement only: no XRPL transaction was submitted "
                f"(placeholder reference {transaction[:12]}...)."
            )
        return f"XRPL payment validated in transaction {transaction}."


def new_state(
    *, run_id: str, goal: ProcurementGoal, policy: WalletPolicy, now: datetime
) -> RunState:
    state = RunState(
        run_id=run_id,
        goal=goal,
        policy=policy,
        created_at=timeutil.iso(now),
        updated_at=timeutil.iso(now),
    )
    state.event(
        "goal_parsed",
        f"Parsed a request for {goal.meal_count} "
        + ", ".join(tag.replace("_", " ") for tag in goal.dietary_tags)
        + f" meals to {goal.destination.zone} by {goal.delivery_deadline} within "
        + f"{drops.to_xrp_label(goal.max_total_spend_drops)}.",
        now,
        related_id=goal.goal_id,
    )
    return state
