import { FlaskConical } from "lucide-react";
import type { AgentRun } from "@/lib/contracts/types";
import { hasSimulatedSettlement } from "@/lib/contracts/settlement";
import { isFixtureMode } from "@/lib/api/config";

/**
 * Says out loud that the payments on screen were simulated.
 *
 * This is the live-mode counterpart to `FixtureBadge`. The buyer agent defaults
 * to `BUYER_AGENT_PAYMENT_MODE=simulated`, so a run can come back from the real
 * API, poll like a real run, and still have settled nothing. Without this, a
 * screenshot of a simulated run is indistinguishable from a real one.
 *
 * Suppressed in fixture mode, where `FixtureBadge` already makes the same point
 * about the whole page and two warnings would just be noise.
 */
export function SettlementNotice({ run }: { run: AgentRun }) {
  if (isFixtureMode) return null;
  if (!hasSimulatedSettlement(run)) return null;

  return (
    <div
      role="status"
      className="flex items-start gap-3 rounded-panel border border-caution/40 bg-caution-dim/40 px-4 py-3"
    >
      <FlaskConical className="mt-0.5 size-4 shrink-0 text-caution" aria-hidden />
      <div className="min-w-0">
        <p className="text-sm font-medium text-caution">
          Simulated settlement — no XRPL transaction was submitted
        </p>
        <p className="mt-1 text-xs leading-relaxed text-ink-muted">
          The buyer agent is running in simulated payment mode, so the hashes below are
          placeholders and the ledger has no record of them. Restart it with{" "}
          <code className="font-mono text-[0.7rem]">BUYER_AGENT_PAYMENT_MODE=x402</code> for real
          Testnet settlement.
        </p>
      </div>
    </div>
  );
}
