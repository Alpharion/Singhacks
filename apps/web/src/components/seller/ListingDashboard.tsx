"use client";

import {
  ArrowDownRight,
  ArrowUpRight,
  Ban,
  CheckCircle2,
  Clock,
  Loader2,
  Minus,
  PackageCheck,
  Radar,
  Sparkles,
  Tag,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";
import { useListing, useRecordDemand, useRecordSale } from "@/lib/seller/queries";
import type {
  ListingEventType,
  ListingStatus,
  PricingAction,
  PricingDecision,
  SellerListing,
} from "@/lib/seller/types";
import { isTerminalListingStatus } from "@/lib/seller/types";
import { Badge, Stat, type Tone } from "@/components/common/Badge";
import { Panel, EmptyState } from "@/components/common/Panel";
import { Money } from "@/components/common/Money";
import { formatClock } from "@/lib/format/time";
import { formatSgd } from "@/lib/format/money";
import { PriceTrack } from "./PriceTrack";
import { cn } from "@/lib/cn";

const STATUS_LABEL: Record<ListingStatus, string> = {
  queued: "Queued",
  parsing: "Reading the listing",
  listed: "Listed",
  repricing: "Pricing live",
  cleared: "Sold out",
  expired: "Window closed",
  withdrawn: "Withdrawn",
};

const STATUS_TONE: Record<ListingStatus, Tone> = {
  queued: "neutral",
  parsing: "neutral",
  listed: "pending",
  repricing: "pending",
  cleared: "rescue",
  expired: "caution",
  withdrawn: "rejected",
};

const EVENT_LABEL: Record<ListingEventType, string> = {
  listing_parsed: "Listing parsed",
  listing_published: "Listed",
  demand_observed: "Buyer interest",
  price_reduced: "Price cut",
  price_raised: "Price raised",
  price_held: "Price held",
  floor_reached: "Floor reached",
  units_sold: "Units sold",
  listing_cleared: "Sold out",
  listing_expired: "Window closed",
};

const EVENT_ICON: Record<ListingEventType, LucideIcon> = {
  listing_parsed: Sparkles,
  listing_published: Tag,
  demand_observed: Radar,
  price_reduced: ArrowDownRight,
  price_raised: ArrowUpRight,
  price_held: Minus,
  floor_reached: Ban,
  units_sold: PackageCheck,
  listing_cleared: CheckCircle2,
  listing_expired: TriangleAlert,
};

const EVENT_TONE: Record<ListingEventType, Tone> = {
  listing_parsed: "neutral",
  listing_published: "neutral",
  demand_observed: "settled",
  price_reduced: "caution",
  price_raised: "rescue",
  price_held: "neutral",
  floor_reached: "rejected",
  units_sold: "rescue",
  listing_cleared: "rescue",
  listing_expired: "caution",
};

const ACTION_TONE: Record<PricingAction, Tone> = {
  open: "neutral",
  reduce: "caution",
  raise: "rescue",
  hold: "neutral",
  floor: "rejected",
};

const TONE_TEXT: Record<Tone, string> = {
  neutral: "text-ink-muted",
  rescue: "text-rescue",
  settled: "text-settled",
  caution: "text-caution",
  rejected: "text-rejected",
  pending: "text-pending",
};

export function ListingDashboard({ listingId }: { listingId: string }) {
  const { listing, isLoading, error } = useListing(listingId);
  const demand = useRecordDemand(listingId);
  const sale = useRecordSale(listingId);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center gap-2.5 py-24 text-sm text-ink-muted">
        <Loader2 className="size-4 animate-spin" aria-hidden />
        Loading listing {listingId}…
      </div>
    );
  }

  if (error || !listing) {
    return (
      <div className="mx-auto max-w-lg py-24 text-center">
        <p className="text-sm font-medium text-rejected">Could not load listing {listingId}</p>
        <p className="mt-1.5 text-sm text-ink-muted">{error?.message}</p>
      </div>
    );
  }

  const closed = isTerminalListingStatus(listing.status);
  const floor = Number(listing.goal.floorUnitPriceDrops);
  const opening = Number(listing.goal.openingUnitPriceDrops);
  const current = Number(listing.unitPriceDrops);
  const abovefloor = current - floor;
  const bandUsed = opening > floor ? 1 - abovefloor / (opening - floor) : 1;

  return (
    <div className="mx-auto max-w-[1400px] space-y-4 px-6 py-6">
      <ListingHeader listing={listing} />

      {/* Both of these have to be stated. A compressed clock that is not
          disclosed overstates how fast the agent works, and simulated buyers
          presented as real would overstate the demand it is reacting to. */}
      {(listing.timeScale > 1 || listing.simulatedMarket) && (
        <p className="flex items-start gap-2 rounded-panel border border-border bg-surface px-4 py-2.5 text-xs leading-relaxed text-ink-muted">
          <Clock className="mt-0.5 size-3.5 shrink-0 text-ink-subtle" aria-hidden />
          <span>
            {listing.timeScale > 1 && (
              <>
                Demo clock: the agent runs its collection window {listing.timeScale}× faster
                than real time, so a whole afternoon of pricing plays out in about a minute.{" "}
              </>
            )}
            {listing.simulatedMarket && (
              <>
                Buyers are simulated in this process — they arrive more readily as the price
                falls. In a joined-up stack these signals come from the buyer agent&apos;s
                discovery calls and settled x402 reservations.
              </>
            )}
          </span>
        </p>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
        <div className="space-y-4">
          <Panel title="What the agent is doing" subtitle="Every move, as it happens">
            <ListingTimeline listing={listing} />
          </Panel>
        </div>

        <div className="space-y-4">
          <Panel
            title="The asking price"
            subtitle="Set by the agent, never below the floor you gave it"
          >
            <div className="mb-4 flex flex-wrap items-end gap-x-8 gap-y-3">
              <div>
                <div className="text-[0.7rem] font-medium uppercase tracking-[0.09em] text-ink-subtle">
                  Asking now
                </div>
                <Money drops={listing.unitPriceDrops} size="xl" tone="text-rescue" />
                <div className="mt-0.5 text-xs text-ink-subtle">per unit</div>
              </div>
              <div>
                <div className="text-[0.7rem] font-medium uppercase tracking-[0.09em] text-ink-subtle">
                  Above your floor
                </div>
                <div className="mt-1 text-xl font-semibold tabular-nums text-ink">
                  {formatSgd(String(abovefloor))}
                </div>
                <div className="mt-0.5 text-xs text-ink-subtle">
                  {Math.round(bandUsed * 100)}% of the band conceded
                </div>
              </div>
            </div>
            <PriceTrack listing={listing} />
          </Panel>

          <Panel
            title="Why it moved the price"
            subtitle="Each call, with the numbers behind it"
          >
            <DecisionList decisions={[...listing.decisions].reverse().slice(0, 8)} />
          </Panel>

          {/* Only offered when nothing is generating demand on its own. With the
              simulated market running, buyers arrive by themselves and a button
              would just be a way to fake what is already happening. */}
          {!closed && !listing.simulatedMarket && (
            <Panel
              title="Simulate the market"
              subtitle="Show the agent reacting to demand rather than describing it"
            >
              <div className="flex flex-wrap gap-2.5">
                <button
                  type="button"
                  onClick={() => demand.mutate(20)}
                  disabled={demand.isPending}
                  className="inline-flex items-center gap-2 rounded-xl bg-settled-dim px-4 py-2.5 text-sm font-medium text-settled ring-1 ring-inset ring-settled/40 transition-colors hover:brightness-105 disabled:opacity-50"
                >
                  <Radar className="size-4" aria-hidden />
                  A buyer enquires
                </button>
                <button
                  type="button"
                  onClick={() => sale.mutate(20)}
                  disabled={sale.isPending || listing.quantityRemaining <= 0}
                  className="inline-flex items-center gap-2 rounded-xl bg-rescue-dim px-4 py-2.5 text-sm font-medium text-rescue ring-1 ring-inset ring-rescue/40 transition-colors hover:brightness-105 disabled:opacity-50"
                >
                  <PackageCheck className="size-4" aria-hidden />
                  Sell 20 units at the current price
                </button>
              </div>
              <p className="mt-3 text-xs leading-relaxed text-ink-subtle">
                In a joined-up stack the buyer agent&apos;s discovery call raises the first
                signal and a settled x402 reservation raises the second. These buttons stand
                in for those while the two agents run separately.
              </p>
            </Panel>
          )}
        </div>
      </div>
    </div>
  );
}

function ListingHeader({ listing }: { listing: SellerListing }) {
  const { goal, revenue } = listing;
  const sold = goal.quantity - listing.quantityRemaining;
  const live = !isTerminalListingStatus(listing.status);

  return (
    <div className="rounded-panel border border-border bg-surface">
      <div className="border-b border-border px-5 py-4">
        <div className="flex items-center gap-2.5">
          <Badge tone={STATUS_TONE[listing.status]}>
            <span
              className={cn("size-1.5 rounded-full bg-current", live && "animate-pulse")}
              aria-hidden
            />
            {STATUS_LABEL[listing.status]}
          </Badge>
          <code className="font-mono text-xs text-ink-subtle">{listing.listingId}</code>
        </div>
        <p className="mt-2.5 max-w-3xl text-[0.95rem] leading-relaxed text-ink">
          {goal.quantity} {goal.dietaryTags.join(" / ")} units, collection by{" "}
          {formatClock(goal.collectionDeadline)}, never below{" "}
          {formatSgd(goal.floorUnitPriceDrops)} each.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-5 px-5 py-4 sm:grid-cols-4">
        <Stat
          label="Sold"
          value={`${sold} / ${goal.quantity}`}
          tone={sold >= goal.quantity ? "rescue" : undefined}
          hint={sold >= goal.quantity ? "Cleared" : `${listing.quantityRemaining} left`}
        />
        <Stat
          label="Earned"
          value={<Money drops={revenue.grossDrops} size="lg" tone="text-settled" />}
          hint={`floor value ${formatSgd(revenue.floorValueDrops)}`}
        />
        <Stat
          label="Above floor"
          value={<Money drops={revenue.upliftDrops} size="lg" tone="text-rescue" />}
          hint="what the agent added"
        />
        <Stat
          label="Your floor"
          value={<Money drops={goal.floorUnitPriceDrops} size="lg" />}
          hint="per unit, never crossed"
        />
      </div>
    </div>
  );
}

function ListingTimeline({ listing }: { listing: SellerListing }) {
  if (listing.events.length === 0) {
    return <EmptyState>The agent has not started yet.</EmptyState>;
  }

  // Newest last, matching the buyer timeline.
  return (
    <ol className="relative space-y-0">
      {listing.events.map((event, index) => {
        const tone = EVENT_TONE[event.eventType];
        const Icon = EVENT_ICON[event.eventType];
        const isLast = index === listing.events.length - 1;

        return (
          <li key={event.sequence} className="animate-beat-in relative flex gap-3.5 pb-5">
            {!isLast && (
              <span
                className="absolute left-[15px] top-8 bottom-0 w-px bg-border"
                aria-hidden
              />
            )}
            <span
              className={cn(
                "relative z-10 grid size-8 shrink-0 place-items-center rounded-full ring-1 ring-inset",
                tone === "rescue" && "bg-rescue-dim ring-rescue/40",
                tone === "settled" && "bg-settled-dim ring-settled/40",
                tone === "caution" && "bg-caution-dim ring-caution/40",
                tone === "rejected" && "bg-rejected-dim ring-rejected/40",
                tone === "pending" && "bg-pending-dim ring-pending/40",
                tone === "neutral" && "bg-surface-raised ring-border",
              )}
            >
              <Icon className={cn("size-4", TONE_TEXT[tone])} aria-hidden />
            </span>
            <div className="min-w-0 flex-1 pt-1">
              <div className="flex flex-wrap items-baseline gap-x-2.5">
                <span className={cn("text-sm font-semibold", TONE_TEXT[tone])}>
                  {EVENT_LABEL[event.eventType]}
                </span>
                <time
                  dateTime={event.createdAt}
                  className="font-mono text-[0.7rem] tabular-nums text-ink-subtle"
                >
                  {formatClock(event.createdAt)}
                </time>
              </div>
              <p className="mt-1 text-sm leading-relaxed text-ink-muted">{event.message}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function DecisionList({ decisions }: { decisions: PricingDecision[] }) {
  if (decisions.length === 0) {
    return <EmptyState>No pricing decisions yet.</EmptyState>;
  }

  return (
    <ul className="space-y-2.5">
      {decisions.map((decision) => (
        <li
          key={decision.decisionId}
          className="animate-beat-in rounded-xl border border-border bg-surface-raised/40 p-4"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Badge tone={ACTION_TONE[decision.action]}>
              {decision.action === "floor" ? "Held at floor" : decision.action}
            </Badge>
            <span className="font-mono text-xs tabular-nums text-ink-muted">
              {formatSgd(decision.previousUnitPriceDrops)} → {" "}
              <span className="font-semibold text-ink">
                {formatSgd(decision.unitPriceDrops)}
              </span>
            </span>
          </div>

          <p className="mt-2.5 text-sm leading-relaxed text-ink">{decision.rationale}</p>

          {decision.reasons.length > 0 && (
            <ul className="mt-2 space-y-1">
              {decision.reasons.map((reason) => (
                <li key={reason} className="flex gap-2 text-xs leading-relaxed text-ink-muted">
                  <span className="text-ink-subtle" aria-hidden>
                    •
                  </span>
                  {reason}
                </li>
              ))}
            </ul>
          )}

          <dl className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-[0.68rem] text-ink-subtle">
            <span>window {Math.round(decision.factors.timeElapsed * 100)}%</span>
            <span>sold {Math.round(decision.factors.sellThrough * 100)}%</span>
            <span>{decision.factors.enquiries} enquiries</span>
            <span>{decision.factors.remaining} unsold</span>
          </dl>
        </li>
      ))}
    </ul>
  );
}
