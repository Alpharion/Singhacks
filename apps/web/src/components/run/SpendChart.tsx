"use client";

import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { AgentRun } from "@/lib/contracts/types";
import { dropsToSgdCents, formatSgd } from "@/lib/format/money";
import { formatXrp } from "@/lib/format/drops";

/**
 * Where the delegated budget went.
 *
 * Drops become a plain number only at the very last step, purely so Recharts has
 * something to scale bars with. Every label still comes from the exact drops
 * string, so nothing displayed has been through a float.
 */
export function SpendChart({ run }: { run: AgentRun }) {
  // Bars are scaled in dollars, since that is what the axis is labelled in.
  const asDollars = (drops: string) => Number(dropsToSgdCents(drops)) / 100;

  const data = [
    {
      key: "food",
      name: "Food",
      sgd: asDollars(run.spend.foodDrops),
      drops: run.spend.foodDrops,
      fill: "var(--color-rescue)",
    },
    {
      key: "delivery",
      name: "Delivery",
      sgd: asDollars(run.spend.deliveryDrops),
      drops: run.spend.deliveryDrops,
      fill: "var(--color-settled)",
    },
    {
      key: "remaining",
      name: "Unspent",
      sgd: asDollars(run.spend.remainingDrops),
      drops: run.spend.remainingDrops,
      fill: "var(--color-border-strong)",
    },
  ];

  return (
    <div>
      <div className="h-[168px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          {/* No negative left margin: it clips three-digit ticks like "120". */}
          <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <XAxis
              dataKey="name"
              tickLine={false}
              axisLine={false}
              tick={{ fill: "var(--color-ink-subtle)", fontSize: 11 }}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              tick={{ fill: "var(--color-ink-subtle)", fontSize: 11 }}
              tickFormatter={(value: number) => `$${value}`}
              width={46}
            />
            <Tooltip
              cursor={{ fill: "var(--color-surface-hover)", opacity: 0.5 }}
              contentStyle={{
                background: "var(--color-surface-raised)",
                border: "1px solid var(--color-border-strong)",
                borderRadius: "0.5rem",
                fontSize: "0.75rem",
              }}
              labelStyle={{ color: "var(--color-ink)" }}
              formatter={(_value, _name, item) => [
                `${formatSgd(item.payload.drops)} · ${formatXrp(item.payload.drops)}`,
                item.payload.name,
              ]}
            />
            <Bar dataKey="sgd" radius={[4, 4, 0, 0]} isAnimationActive={false}>
              {data.map((entry) => (
                <Cell key={entry.key} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <dl className="mt-3 grid grid-cols-3 gap-3 border-t border-border pt-3 text-xs">
        {data.map((entry) => (
          <div key={entry.key}>
            <dt className="flex items-center gap-1.5 text-ink-subtle">
              <span
                className="size-2 rounded-sm"
                style={{ background: entry.fill }}
                aria-hidden
              />
              {entry.name}
            </dt>
            <dd className="mt-1 font-medium tabular-nums text-ink">
              {formatSgd(entry.drops)}
            </dd>
            <dd className="text-[0.68rem] tabular-nums text-ink-subtle">
              {formatXrp(entry.drops)}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
