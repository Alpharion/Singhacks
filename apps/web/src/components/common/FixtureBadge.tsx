import { FlaskConical } from "lucide-react";
import { isFixtureMode } from "@/lib/api/config";

/**
 * States plainly that the run on screen is replayed fixture data.
 *
 * The contract fixtures carry synthetic transaction hashes and unfunded
 * addresses. Without this, a screenshot of the dashboard would imply an XRPL
 * settlement that never happened. It disappears the moment the app is pointed
 * at the live buyer agent.
 */
export function FixtureBadge() {
  if (!isFixtureMode) return null;

  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full bg-caution-dim px-2.5 py-1 text-xs font-medium text-caution ring-1 ring-inset ring-caution/30"
      title="Replayed contract fixtures. Transaction hashes are synthetic placeholders and no XRPL settlement has occurred."
    >
      <FlaskConical className="size-3.5" aria-hidden />
      Demo data — no XRPL settlement
    </span>
  );
}
