import { ArrowRight, ShieldCheck, X } from "lucide-react";
import type { AgentDecision } from "@/lib/contracts/types";
import { decisionHash } from "@/lib/contracts/types";
import { formatSgd } from "@/lib/format/money";
import { formatClock } from "@/lib/format/time";
import { Badge } from "@/components/common/Badge";
import { DECISION_LABEL, DECISION_TONE } from "@/components/common/status";
import { TxHash } from "@/components/common/Xrpl";
import { EmptyState } from "@/components/common/Panel";

/**
 * The agent's reasoning, as the contract records it.
 *
 * Each decision carries what it was trying to do, what it weighed, why it chose
 * what it chose, and why it turned the rest down. This is the audit trail that
 * makes an autonomous payment defensible after the fact.
 */
export function DecisionList({ decisions }: { decisions: AgentDecision[] }) {
  if (decisions.length === 0) {
    return <EmptyState>The agent has not made a decision yet.</EmptyState>;
  }

  return (
    <ul className="space-y-3">
      {decisions.map((decision) => (
        <li key={decision.decisionId}>
          <DecisionCard decision={decision} />
        </li>
      ))}
    </ul>
  );
}

function DecisionCard({ decision }: { decision: AgentDecision }) {
  const hash = decisionHash(decision);

  return (
    <article className="animate-beat-in rounded-xl border border-border bg-canvas p-4">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <Badge tone={DECISION_TONE[decision.decisionType]}>
          {DECISION_LABEL[decision.decisionType]}
        </Badge>
        <time
          dateTime={decision.createdAt}
          className="font-mono text-[0.7rem] tabular-nums text-ink-subtle"
        >
          {formatClock(decision.createdAt)}
        </time>
      </header>

      <p className="mt-3 text-sm leading-relaxed text-ink">{decision.objective}</p>

      {decision.selectedOptionId && (
        <div className="mt-3 flex items-center gap-2 text-xs">
          <ArrowRight className="size-3.5 shrink-0 text-rescue" aria-hidden />
          <span className="text-ink-subtle">Chose</span>
          <code className="font-mono text-rescue">{decision.selectedOptionId}</code>
        </div>
      )}

      <ul className="mt-3 space-y-1.5">
        {decision.reasons.map((reason, index) => (
          <li key={index} className="flex gap-2 text-sm leading-relaxed text-ink-muted">
            <span className="mt-[0.45rem] size-1 shrink-0 rounded-full bg-ink-subtle" aria-hidden />
            {reason}
          </li>
        ))}
      </ul>

      {decision.rejectedAlternatives.length > 0 && (
        <div className="mt-3.5 space-y-2 rounded-lg bg-rejected-dim/40 p-3">
          {decision.rejectedAlternatives.map((rejected) => (
            <div key={rejected.optionId} className="flex gap-2">
              <X className="mt-0.5 size-3.5 shrink-0 text-rejected" aria-hidden />
              <div className="min-w-0">
                <code className="font-mono text-[0.7rem] text-rejected">
                  {rejected.optionId}
                </code>
                {rejected.reasons.map((reason, index) => (
                  <p key={index} className="mt-0.5 text-xs leading-relaxed text-ink-muted">
                    {reason}
                  </p>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <footer className="mt-3.5 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-border pt-3 text-xs">
        <span className="text-ink-subtle">
          Budget left{" "}
          <span className="font-medium tabular-nums text-ink">
            {formatSgd(decision.remainingBudgetDrops)}
          </span>
        </span>
        <span className="inline-flex items-center gap-1.5 text-ink-subtle">
          <ShieldCheck className="size-3.5" aria-hidden />
          <code className="font-mono">{decision.walletPolicyId}</code>
        </span>
        {hash && <TxHash hash={hash} />}
      </footer>
    </article>
  );
}
