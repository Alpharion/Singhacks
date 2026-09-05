import { ArrowRight, Clock, ShieldCheck, TrendingDown } from "lucide-react";
import { Panel } from "@/components/common/Panel";
import { ListingForm } from "@/components/seller/ListingForm";

const LOOP = [
  {
    icon: ShieldCheck,
    title: "You set the floor",
    body: "One number the agent may never go under. That is the whole of your instruction, and it is enforced in code rather than promised by a model.",
  },
  {
    icon: TrendingDown,
    title: "It prices against the clock",
    body: "Surplus is worth nothing once it is thrown away, so the agent concedes margin as the collection deadline approaches — and holds firm while stock is still moving.",
  },
  {
    icon: Clock,
    title: "It answers demand",
    body: "Buyer interest pushes the price back up. Every move is recorded with the numbers behind it, so you can audit why your food was ever offered at a given price.",
  },
];

export default function SellPage() {
  return (
    <div className="bg-grid">
      <div className="mx-auto max-w-[1400px] px-6 py-12 lg:py-16">
        <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_400px] lg:gap-14">
          <div className="max-w-2xl">
            <p className="text-[0.7rem] font-medium uppercase tracking-[0.14em] text-rescue">
              The other side of the same market
            </p>
            <h1 className="mt-3 text-4xl font-semibold leading-[1.1] tracking-tight text-ink lg:text-5xl">
              By closing time, unsold food is worth nothing at all.
            </h1>
            <p className="mt-5 text-lg leading-relaxed text-ink-muted">
              A bakery with sixty vegetarian boxes at four in the afternoon has a pricing
              problem no one has time to solve. Hold out for full price and the stock is
              binned. Discount too early and you give away margin you did not need to.
            </p>
            <p className="mt-4 text-lg leading-relaxed text-ink-muted">
              SurplusFlow gives that problem to an agent too. You state the floor. It works
              the price between there and your opening ask, reacting to the clock, to what
              has sold, and to who is asking.
            </p>

            <ul className="mt-10 space-y-5">
              {LOOP.map(({ icon: Icon, title, body }, index) => (
                <li key={title} className="flex gap-4">
                  <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-surface-raised ring-1 ring-inset ring-border">
                    <Icon className="size-4 text-rescue" aria-hidden />
                  </span>
                  <div className="min-w-0 pt-0.5">
                    <h2 className="text-sm font-semibold text-ink">
                      <span className="mr-2 text-ink-subtle tabular-nums">0{index + 1}</span>
                      {title}
                    </h2>
                    <p className="mt-1 text-sm leading-relaxed text-ink-muted">{body}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>

          <div className="space-y-5">
            <Panel title="New listing" subtitle="Green Oven Bakery · Queenstown">
              <ListingForm />
            </Panel>

            <p className="flex items-center justify-center gap-1.5 text-xs text-ink-subtle">
              Listing opens the live pricing console
              <ArrowRight className="size-3" aria-hidden />
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
