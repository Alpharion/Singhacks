"use client";

import {
  Area,
  AreaChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  YAxis,
} from "recharts";
import type { SellerListing } from "@/lib/seller/types";
import { formatSgd } from "@/lib/format/money";
import { formatXrp } from "@/lib/format/drops";

/**
 * The price the agent has been asking, against the floor it may not cross.
 *
 * The floor is drawn as a hard line for a reason: the whole delegation rests on
 * the price never going under it, so the constraint should be as visible as the
 * behaviour.
 */
export function PriceTrack({ listing }: { listing: SellerListing }) {
  const floor = Number(listing.goal.floorUnitPriceDrops);
  const opening = Number(listing.goal.openingUnitPriceDrops);

  const points = [
    { index: 0, price: opening, label: "Opened" },
    ...listing.decisions.map((decision, position) => ({
      index: position + 1,
      price: Number(decision.unitPriceDrops),
      label: decision.action,
    })),
  ];

  if (points.length < 2) {
    return (
      <p className="py-8 text-center text-sm text-ink-muted">
        The agent has not repriced yet.
      </p>
    );
  }

  // Leave headroom below the floor so the reference line is never on the axis.
  const band = Math.max(opening - floor, 1);

  return (
    <div className="h-44 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="priceFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--color-rescue)" stopOpacity={0.35} />
              <stop offset="100%" stopColor="var(--color-rescue)" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <YAxis
            domain={[floor - band * 0.15, opening + band * 0.08]}
            tick={{ fontSize: 10 }}
            width={58}
            tickFormatter={(value: number) => formatXrp(String(Math.round(value)))}
            stroke="var(--color-ink-subtle)"
          />
          <ReferenceLine
            y={floor}
            stroke="var(--color-rejected)"
            strokeDasharray="4 3"
            label={{
              value: `floor ${formatXrp(listing.goal.floorUnitPriceDrops)}`,
              position: "insideBottomLeft",
              fontSize: 10,
              fill: "var(--color-rejected)",
            }}
          />
          <Tooltip
            contentStyle={{
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: 10,
              fontSize: 12,
            }}
            formatter={(value) => {
              const drops = String(Math.round(Number(value ?? 0)));
              return [`${formatXrp(drops)} · ${formatSgd(drops)}`, "Unit price"];
            }}
            labelFormatter={() => ""}
          />
          <Area
            type="stepAfter"
            dataKey="price"
            stroke="var(--color-rescue)"
            strokeWidth={2}
            fill="url(#priceFill)"
            isAnimationActive={false}
            dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
