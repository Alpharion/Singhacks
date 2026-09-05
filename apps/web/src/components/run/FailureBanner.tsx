import { TriangleAlert } from "lucide-react";
import type { ApiError } from "@/lib/contracts/types";
import { Badge } from "@/components/common/Badge";
import { ERROR_LABEL } from "@/components/common/status";

/**
 * Renders `AgentRun.failure`, which the contract types as an `ApiError`.
 *
 * `retryable` matters to the story: a retryable provider failure is what the
 * agent recovers from by replanning, rather than something the buyer has to
 * deal with.
 */
export function FailureBanner({ failure }: { failure: ApiError }) {
  return (
    <div className="rounded-panel border border-rejected/35 bg-rejected-dim/40 px-5 py-4">
      <div className="flex flex-wrap items-center gap-2.5">
        <TriangleAlert className="size-4 shrink-0 text-rejected" aria-hidden />
        <span className="text-sm font-semibold text-ink">
          {ERROR_LABEL[failure.error] ?? failure.error}
        </span>
        <Badge tone={failure.retryable ? "caution" : "rejected"}>
          {failure.retryable ? "Retryable" : "Terminal"}
        </Badge>
      </div>

      <p className="mt-2 text-sm leading-relaxed text-ink-muted">{failure.message}</p>

      <code className="mt-2 inline-block font-mono text-[0.68rem] text-ink-subtle">
        {failure.requestId}
      </code>
    </div>
  );
}
