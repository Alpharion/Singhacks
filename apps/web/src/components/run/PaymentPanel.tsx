import { FlaskConical, Receipt } from "lucide-react";
import type { AgentRun, PaymentReceipt, PaymentRequirement } from "@/lib/contracts/types";
import { explorerUrl, receiptHash } from "@/lib/contracts/types";
import { isSimulatedReceipt } from "@/lib/contracts/settlement";
import { Money } from "@/components/common/Money";
import { formatDateTime } from "@/lib/format/time";
import { Badge } from "@/components/common/Badge";
import { EmptyState } from "@/components/common/Panel";
import { ExplorerLink, TxHash, XrplAddr } from "@/components/common/Xrpl";

/**
 * Every payment this run made, plus any outstanding x402 challenge.
 *
 * A `PaymentReceipt` only exists for a settled, validated payment - the schema
 * pins `success` and `validated` to `true`. Failures never appear here; they
 * arrive as an `ApiError` and are shown by the failure banner instead.
 */
export function PaymentPanel({
  run,
  challenge,
}: {
  run: AgentRun;
  challenge?: PaymentRequirement;
}) {
  const receipts: Array<{ receipt: PaymentReceipt; label: string; forWhat: string }> = [
    ...run.reservations.map((reservation) => ({
      receipt: reservation.paymentReceipt,
      label: "Food reservation",
      forWhat: `${reservation.quantity} meals · ${reservation.sellerId}`,
    })),
    ...run.deliveryBookings.map((booking) => ({
      receipt: booking.paymentReceipt,
      label: "Courier booking",
      forWhat: booking.providerId,
    })),
  ];

  if (!challenge && receipts.length === 0) {
    return <EmptyState>Nobody has asked for payment yet.</EmptyState>;
  }

  return (
    <div className="space-y-4">
      {challenge && <ChallengeCard challenge={challenge} />}

      {receipts.length > 0 && (
        <ul className="space-y-2.5">
          {receipts.map(({ receipt, label, forWhat }) => (
            <li key={receiptHash(receipt)}>
              <ReceiptCard receipt={receipt} label={label} forWhat={forWhat} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/**
 * The decoded HTTP 402 response.
 *
 * Over the wire this is a base64 `PAYMENT-REQUIRED` header on a 402; it is
 * decoded here so the demo can show what the provider actually demanded before
 * any money moved.
 */
function ChallengeCard({ challenge }: { challenge: PaymentRequirement }) {
  const accept = challenge.accepts[0];
  if (!accept) return null;

  return (
    <div className="animate-beat-in rounded-xl border border-pending/30 bg-pending-dim/40 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="rounded-md bg-pending/15 px-2 py-1 font-mono text-xs font-semibold text-pending">
            HTTP 402
          </span>
          <span className="text-sm font-medium text-ink">Payment required</span>
        </div>
        <Badge tone="pending">x402 v{challenge.x402Version}</Badge>
      </div>

      <p className="mt-2.5 text-xs leading-relaxed text-ink-muted">
        The provider answered the reservation request with a price instead of the goods. No
        human was involved in reading it.
      </p>

      <dl className="mt-3.5 grid grid-cols-2 gap-x-5 gap-y-2.5 text-xs sm:grid-cols-3">
        {/* XRP leads on settlement figures: this is what the ledger is being
            asked to move, and it has to be checkable against the explorer. */}
        <Field label="Amount" value={<Money drops={accept.amount} lead="xrp" size="sm" />} />
        <Field label="Scheme" value={accept.scheme} />
        <Field label="Network" value={accept.network} />
        <Field label="Pay to" value={<XrplAddr address={accept.payTo} />} />
        <Field label="Timeout" value={`${accept.maxTimeoutSeconds}s`} />
        <Field
          label="Invoice"
          value={
            <code className="font-mono text-[0.68rem] text-ink-muted">
              {accept.extra.invoiceId}
            </code>
          }
        />
      </dl>
    </div>
  );
}

function ReceiptCard({
  receipt,
  label,
  forWhat,
}: {
  receipt: PaymentReceipt;
  label: string;
  forWhat: string;
}) {
  // A simulated receipt is schema-valid but settled nothing, so it must not be
  // dressed in the settled colours or linked as if an explorer could show it.
  const simulated = isSimulatedReceipt(receipt);

  return (
    <article
      className={
        simulated
          ? "animate-beat-in rounded-xl border border-caution/30 bg-caution-dim/30 p-4"
          : "animate-beat-in rounded-xl border border-settled/30 bg-settled-dim/30 p-4"
      }
    >
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          {simulated ? (
            <FlaskConical className="size-4 text-caution" aria-hidden />
          ) : (
            <Receipt className="size-4 text-settled" aria-hidden />
          )}
          <span className="text-sm font-medium text-ink">{label}</span>
        </div>
        {simulated ? (
          <Badge tone="caution" className="cursor-help">
            <span title="The buyer agent is running in simulated payment mode. This hash is a placeholder and no XRPL transaction was submitted.">
              Simulated — not settled on XRPL
            </span>
          </Badge>
        ) : (
          <Badge tone="settled">Validated on XRPL</Badge>
        )}
      </header>

      <p className="mt-1.5 text-xs text-ink-subtle">{forWhat}</p>

      <dl className="mt-3.5 grid grid-cols-2 gap-x-5 gap-y-2.5 text-xs sm:grid-cols-3">
        <Field label="Amount" value={<Money drops={receipt.amountDrops} lead="xrp" size="sm" />} />
        <Field label="From" value={<XrplAddr address={receipt.payer} />} />
        <Field label="To" value={<XrplAddr address={receipt.payee} />} />
        <Field label="Settled" value={formatDateTime(receipt.validatedAt)} />
        <Field
          label="Invoice"
          value={
            <code className="font-mono text-[0.68rem] text-ink-muted">{receipt.invoiceId}</code>
          }
        />
        <Field
          label="Transaction"
          value={
            simulated ? (
              // No explorer link: the URL points at the agent's own placeholder
              // route, and rendering it as an explorer link would imply the
              // ledger has something to show.
              <TxHash hash={receiptHash(receipt)} className="text-caution" />
            ) : (
              <ExplorerLink url={explorerUrl(receipt)} hash={receiptHash(receipt)} />
            )
          }
        />
      </dl>
    </article>
  );
}

function Field({
  label,
  value,
  emphasis,
}: {
  label: string;
  value: React.ReactNode;
  emphasis?: boolean;
}) {
  return (
    <div className="min-w-0">
      <dt className="text-[0.62rem] uppercase tracking-[0.08em] text-ink-subtle">{label}</dt>
      <dd
        className={
          emphasis
            ? "mt-0.5 text-sm font-semibold tabular-nums text-ink"
            : "mt-0.5 truncate text-ink-muted"
        }
      >
        {value}
      </dd>
    </div>
  );
}
