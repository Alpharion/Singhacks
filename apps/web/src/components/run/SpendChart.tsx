"use client";

import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { AgentRun } from "@/lib/contracts/types";
import { dropsToXrpString, formatXrp } from "@/lib/format/drops";

/**
 * Where the delegated budget went.
 *
 * Drops are converted to XRP only at the very last step, purely so Recharts has
 * a number to scale bars with. Every label still comes from the exact drops
 * string, so nothing displayed has been through a float.
 */
export function SpendChart({ run }: { run: AgentRun }) {
  const data = [
    {
      key: "food",
      name: "Food",
      xrp: Number(dropsToXrpString(run.spend.foodDrops)),
      drops: run.spend.foodDrops,
      fill: "var(--color-rescue)",
    },
    {
      key: "delivery",
      name: "Delivery",
      xrp: Number(dropsToXrpString(run.spend.deliveryDrops)),
      drops: run.spend.deliveryDrops,
      fill: "var(--color-settled)",
    },
    {
      key: "remaining",
      name: "Unspent",
      xrp: Number(dropsToXrpString(run.spend.remainingDrops)),
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
              width={38}
              unit=""
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
                formatXrp(item.payload.drops),
                item.payload.name,
              ]}
            />
            <Bar dataKey="xrp" radius={[4, 4, 0, 0]} isAnimationActive={false}>
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
            <dd className="mt-1 font-medium tabular-nums text-ink">{formatXrp(entry.drops)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
