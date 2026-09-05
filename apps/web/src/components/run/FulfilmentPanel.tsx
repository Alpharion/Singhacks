"use client";

import QRCode from "react-qr-code";
import { PackageCheck, Truck } from "lucide-react";
import type { AgentRun, DeliveryBooking, Reservation } from "@/lib/contracts/types";
import { formatWindow, formatClock } from "@/lib/format/time";
import { formatXrp } from "@/lib/format/drops";
import { Badge, type Tone } from "@/components/common/Badge";
import { EmptyState } from "@/components/common/Panel";

const RESERVATION_TONE: Record<Reservation["status"], Tone> = {
  confirmed: "rescue",
  expired: "caution",
  cancelled: "rejected",
  failed: "rejected",
};

const BOOKING_TONE: Record<DeliveryBooking["status"], Tone> = {
  confirmed: "rescue",
  collecting: "settled",
  in_transit: "settled",
  delivered: "rescue",
  cancelled: "rejected",
  failed: "rejected",
};

/**
 * What the payments actually bought.
 *
 * This is the point of the whole exercise: settlement returns an exclusive hold
 * on real inventory and a booked courier, not just a transaction hash.
 */
export function FulfilmentPanel({ run }: { run: AgentRun }) {
  if (run.reservations.length === 0 && run.deliveryBookings.length === 0) {
    return <EmptyState>Nothing has been reserved yet.</EmptyState>;
  }

  const sellerNameFor = (sellerId: string) =>
    run.offers.find((offer) => offer.sellerId === sellerId)?.sellerName ?? sellerId;

  const courierNameFor = (providerId: string) =>
    run.deliveryQuotes.find((quote) => quote.providerId === providerId)?.providerName ??
    providerId;

  return (
    <div className="space-y-3">
      {run.reservations.map((reservation) => (
        <ReservationCard
          key={reservation.reservationId}
          reservation={reservation}
          sellerName={sellerNameFor(reservation.sellerId)}
        />
      ))}
      {run.deliveryBookings.map((booking) => (
        <DeliveryCard
          key={booking.bookingId}
          booking={booking}
          courierName={courierNameFor(booking.providerId)}
        />
      ))}
    </div>
  );
}

function ReservationCard({
  reservation,
  sellerName,
}: {
  reservation: Reservation;
  sellerName: string;
}) {
  return (
    <article className="animate-beat-in flex flex-wrap items-start gap-4 rounded-xl border border-border bg-canvas/40 p-4">
      <div className="min-w-0 flex-1">
        <header className="flex flex-wrap items-center gap-2">
          <PackageCheck className="size-4 text-rescue" aria-hidden />
          <span className="text-sm font-semibold text-ink">{sellerName}</span>
          <Badge tone={RESERVATION_TONE[reservation.status]}>{reservation.status}</Badge>
        </header>

        <p className="mt-2 text-sm text-ink">
          <span className="font-semibold tabular-nums">{reservation.quantity}</span> meals held
          for collection
        </p>

        <dl className="mt-2.5 space-y-1 text-xs">
          <Row label="Pickup window" value={formatWindow(reservation.pickupWindow)} />
          <Row label="Paid" value={formatXrp(reservation.paymentReceipt.amountDrops)} />
          <Row label="Reservation" value={reservation.reservationId} mono />
        </dl>
      </div>

      {reservation.pickupToken && (
        <figure className="shrink-0 text-center">
          {/* Rendered white-on-white so scanners read it reliably off a dark UI. */}
          <div className="rounded-lg bg-white p-2">
            <QRCode
              value={reservation.pickupToken}
              size={84}
              level="M"
              bgColor="#ffffff"
              fgColor="#080b10"
            />
          </div>
          <figcaption className="mt-1.5 text-[0.62rem] uppercase tracking-[0.08em] text-ink-subtle">
            Pickup token
          </figcaption>
        </figure>
      )}
    </article>
  );
}

function DeliveryCard({
  booking,
  courierName,
}: {
  booking: DeliveryBooking;
  courierName: string;
}) {
  return (
    <article className="animate-beat-in rounded-xl border border-border bg-canvas/40 p-4">
      <header className="flex flex-wrap items-center gap-2">
        <Truck className="size-4 text-settled" aria-hidden />
        <span className="text-sm font-semibold text-ink">{courierName}</span>
        <Badge tone={BOOKING_TONE[booking.status]}>{booking.status.replace(/_/g, " ")}</Badge>
      </header>

      <dl className="mt-2.5 space-y-1 text-xs">
        <Row label="Collects" value={formatClock(booking.pickupEta)} />
        <Row label="Arrives" value={formatClock(booking.deliveryEta)} />
        <Row label="Paid" value={formatXrp(booking.paymentReceipt.amountDrops)} />
        <Row label="Tracking" value={booking.trackingCode} mono />
      </dl>
    </article>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-ink-subtle">{label}</dt>
      <dd className={mono ? "font-mono text-[0.7rem] text-ink-muted" : "tabular-nums text-ink"}>
        {value}
      </dd>
    </div>
  );
}
