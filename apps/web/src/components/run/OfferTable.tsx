import { Ban } from "lucide-react";
import type { AgentRun, DeliveryQuote, FoodOffer } from "@/lib/contracts/types";
import { formatXrpCompact } from "@/lib/format/drops";
import { formatClock } from "@/lib/format/time";
import { Badge } from "@/components/common/Badge";
import { EmptyState } from "@/components/common/Panel";
import { cn } from "@/lib/cn";

/**
 * Build a map of optionId -> rejection reasons from the agent's decisions.
 *
 * Rejection is not a property of the offer: `offer_grill_001` keeps
 * `status: "available"` throughout, because it is a perfectly good offer that
 * simply fails this buyer's dietary rule. The judgement lives in
 * `AgentDecision.rejectedAlternatives`, so that is what we read.
 */
function rejectionsFrom(run: AgentRun): Map<string, string[]> {
  const rejections = new Map<string, string[]>();
  for (const decision of run.decisions) {
    for (const rejected of decision.rejectedAlternatives) {
      const existing = rejections.get(rejected.optionId) ?? [];
      rejections.set(rejected.optionId, [...existing, ...rejected.reasons]);
    }
  }
  return rejections;
}

export function OfferTable({ run }: { run: AgentRun }) {
  const rejections = rejectionsFrom(run);

  if (run.offers.length === 0 && run.deliveryQuotes.length === 0) {
    return <EmptyState>Discovery has not run yet.</EmptyState>;
  }

  const selectedPlan = run.plans.find((plan) => plan.planId === run.selectedPlanId);
  const chosenOfferIds = new Set(
    selectedPlan?.foodAllocations.map((allocation) => allocation.offerId) ?? [],
  );

  return (
    <div className="space-y-6">
      {run.offers.length > 0 && (
        <Section title="Food offers" count={run.offers.length}>
          {run.offers.map((offer) => (
            <OfferRow
              key={offer.offerId}
              offer={offer}
              rejectionReasons={rejections.get(offer.offerId)}
              isChosen={chosenOfferIds.has(offer.offerId)}
              chosenQuantity={
                selectedPlan?.foodAllocations.find((a) => a.offerId === offer.offerId)?.quantity
              }
            />
          ))}
        </Section>
      )}

      {run.deliveryQuotes.length > 0 && (
        <Section title="Courier quotes" count={run.deliveryQuotes.length}>
          {run.deliveryQuotes.map((quote) => (
            <QuoteRow
              key={quote.quoteId}
              quote={quote}
              rejectionReasons={rejections.get(quote.quoteId)}
              isChosen={selectedPlan?.deliveryQuoteId === quote.quoteId}
            />
          ))}
        </Section>
      )}
    </div>
  );
}

function Section({
  title,
  count,
  children,
}: {
  title: string;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <div>
      <h3 className="mb-2.5 flex items-baseline gap-2 text-[0.7rem] font-medium uppercase tracking-[0.09em] text-ink-subtle">
        {title}
        <span className="tabular-nums text-ink-subtle/70">{count}</span>
      </h3>
      <ul className="space-y-2">{children}</ul>
    </div>
  );
}

function RowShell({
  isChosen,
  isRejected,
  children,
}: {
  isChosen: boolean;
  isRejected: boolean;
  children: React.ReactNode;
}) {
  return (
    <li
      className={cn(
        "rounded-xl border px-4 py-3 transition-colors",
        isChosen
          ? "border-rescue/40 bg-rescue-dim/40"
          : isRejected
            ? "border-border bg-canvas/40 opacity-70"
            : "border-border bg-canvas/40",
      )}
    >
      {children}
    </li>
  );
}

function RejectionNote({ reasons }: { reasons: string[] }) {
  return (
    <div className="mt-2.5 flex gap-2 rounded-lg bg-rejected-dim/60 px-2.5 py-2">
      <Ban className="mt-0.5 size-3.5 shrink-0 text-rejected" aria-hidden />
      <div className="min-w-0 text-xs leading-relaxed text-rejected">
        {reasons.map((reason, index) => (
          <p key={index}>{reason}</p>
        ))}
      </div>
    </div>
  );
}

function OfferRow({
  offer,
  rejectionReasons,
  isChosen,
  chosenQuantity,
}: {
  offer: FoodOffer;
  rejectionReasons?: string[];
  isChosen: boolean;
  chosenQuantity?: number;
}) {
  const isRejected = Boolean(rejectionReasons?.length);

  return (
    <RowShell isChosen={isChosen} isRejected={isRejected}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-ink">{offer.sellerName}</span>
            {isChosen && (
              <Badge tone="rescue">
                Selected{chosenQuantity ? ` · ${chosenQuantity} meals` : ""}
              </Badge>
            )}
            {isRejected && <Badge tone="rejected">Rejected</Badge>}
          </div>
          <p className="mt-1 text-xs text-ink-muted">{offer.title}</p>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {offer.dietaryTags.map((tag) => (
              <span
                key={tag}
                className="rounded bg-surface-raised px-1.5 py-0.5 text-[0.68rem] capitalize text-ink-subtle"
              >
                {tag.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        </div>

        <dl className="flex shrink-0 gap-5 text-right">
          <Metric label="Unit" value={formatXrpCompact(offer.unitPriceDrops)} />
          <Metric label="Available" value={`${offer.quantityAvailable}`} />
          <Metric
            label="Reliability"
            value={`${(offer.reliabilityScore * 100).toFixed(0)}%`}
          />
          <Metric label="Expires" value={formatClock(offer.expiresAt)} />
        </dl>
      </div>

      {rejectionReasons?.length ? <RejectionNote reasons={rejectionReasons} /> : null}
    </RowShell>
  );
}

function QuoteRow({
  quote,
  rejectionReasons,
  isChosen,
}: {
  quote: DeliveryQuote;
  rejectionReasons?: string[];
  isChosen: boolean;
}) {
  const isUnavailable = quote.status !== "available";
  const isRejected = Boolean(rejectionReasons?.length) || isUnavailable;

  return (
    <RowShell isChosen={isChosen} isRejected={isRejected}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-ink">{quote.providerName}</span>
            {isChosen && <Badge tone="rescue">Booked</Badge>}
            {isUnavailable && <Badge tone="caution">{quote.status}</Badge>}
          </div>
          <p className="mt-1 text-xs text-ink-muted">
            Collects from {quote.pickupSellerIds.length} sellers · to {quote.destinationZone}
          </p>
        </div>

        <dl className="flex shrink-0 gap-5 text-right">
          <Metric label="Price" value={formatXrpCompact(quote.priceDrops)} />
          <Metric label="Capacity" value={`${quote.capacityMeals}`} />
          <Metric
            label="Reliability"
            value={`${(quote.reliabilityScore * 100).toFixed(0)}%`}
          />
          <Metric label="Arrives" value={formatClock(quote.deliveryEta)} />
        </dl>
      </div>

      {rejectionReasons?.length ? <RejectionNote reasons={rejectionReasons} /> : null}
    </RowShell>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[0.62rem] uppercase tracking-[0.08em] text-ink-subtle">{label}</dt>
      <dd className="mt-0.5 text-sm font-medium tabular-nums text-ink">{value}</dd>
    </div>
  );
}
