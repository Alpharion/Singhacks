import { ArrowRight, Boxes, HandCoins, Sparkles } from "lucide-react";
import { Panel } from "@/components/common/Panel";
import { ProcurementForm } from "@/components/procurement/ProcurementForm";
import { AuthorityCard } from "@/components/procurement/AuthorityCard";
import { demoPolicy, fixtureRun } from "@/lib/demo/fixtures";

const LOOP = [
  {
    icon: Sparkles,
    title: "Understand and discover",
    body: "One sentence becomes typed constraints. The agent pulls live offers from every seller and courier.",
  },
  {
    icon: Boxes,
    title: "Decide and explain",
    body: "It rejects what does not qualify, combines sellers to reach the quantity, and says why it picked the plan it did.",
  },
  {
    icon: HandCoins,
    title: "Pay and receive value",
    body: "Providers answer with HTTP 402. The agent settles on XRPL and gets back an exclusive reservation.",
  },
];

export default function HomePage() {
  return (
    <div className="bg-grid">
      <div className="mx-auto max-w-[1400px] px-6 py-12 lg:py-16">
        <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_400px] lg:gap-14">
          {/* Pitch */}
          <div className="max-w-2xl">
            <p className="text-[0.7rem] font-medium uppercase tracking-[0.14em] text-rescue">
              Agentic procurement on the XRP Ledger
            </p>
            <h1 className="mt-3 text-4xl font-semibold leading-[1.1] tracking-tight text-ink lg:text-5xl">
              Surplus food expires faster than a human can buy it.
            </h1>
            <p className="mt-5 text-lg leading-relaxed text-ink-muted">
              A community kitchen needs a hundred meals by six. The right surplus exists —
              scattered across a bakery, a hotel and a supermarket, priced differently, expiring
              at different times, and gone if someone else books it first.
            </p>
            <p className="mt-4 text-lg leading-relaxed text-ink-muted">
              SurplusFlow gives that problem to an agent. You set the budget and the rules. It
              finds the combination, pays each provider over x402 on XRPL, and hands back
              confirmed reservations before the food is thrown away.
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

          {/* Request + delegated authority */}
          <div className="space-y-5">
            <Panel
              title="New procurement request"
              subtitle="Community kitchen · Queenstown"
            >
              <ProcurementForm />
            </Panel>

            <Panel
              title="Authority you delegate"
              subtitle="Enforced in code, not by the model"
            >
              <AuthorityCard goal={fixtureRun.goal} policy={demoPolicy} />
            </Panel>

            <p className="flex items-center justify-center gap-1.5 text-xs text-ink-subtle">
              Dispatching opens the live agent console
              <ArrowRight className="size-3" aria-hidden />
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
