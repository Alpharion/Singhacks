"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowRight, Loader2 } from "lucide-react";
import { useStartProcurement } from "@/lib/queries";
import { fixtureProcurementRequest } from "@/lib/demo/fixtures";
import { cn } from "@/lib/cn";

/**
 * The only thing the human does: state the objective in one sentence.
 *
 * Everything downstream - which sellers, how many meals from each, which
 * courier, how much to pay - is the agent's decision inside the authority set
 * out beside this form.
 */
export function ProcurementForm() {
  const router = useRouter();
  const startProcurement = useStartProcurement();
  const [requestText, setRequestText] = useState(fixtureProcurementRequest.requestText);

  const isSubmitting = startProcurement.isPending;
  const tooShort = requestText.trim().length < 10;

  async function handleSubmit(formEvent: React.FormEvent) {
    formEvent.preventDefault();
    if (tooShort || isSubmitting) return;

    const run = await startProcurement.mutateAsync({
      buyerId: fixtureProcurementRequest.buyerId,
      requestText: requestText.trim(),
      walletPolicyId: fixtureProcurementRequest.walletPolicyId,
    });

    router.push(`/runs/${run.runId}`);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label
          htmlFor="requestText"
          className="block text-[0.7rem] font-medium uppercase tracking-[0.09em] text-ink-subtle"
        >
          What do you need?
        </label>
        <textarea
          id="requestText"
          name="requestText"
          rows={4}
          value={requestText}
          onChange={(changeEvent) => setRequestText(changeEvent.target.value)}
          maxLength={1000}
          className={cn(
            "mt-2 w-full resize-none rounded-xl border border-border bg-canvas px-4 py-3.5",
            "text-[0.95rem] leading-relaxed text-ink placeholder:text-ink-subtle",
            "outline-none transition-colors focus:border-rescue/50 focus:ring-2 focus:ring-rescue/15",
          )}
          placeholder="Secure 100 vegetarian meals, delivered by 6 PM, for no more than 120 XRP including delivery."
        />
        <p className="mt-1.5 text-xs text-ink-subtle">
          Plain language. The agent turns this into quantity, dietary, deadline, and budget
          constraints.
        </p>
      </div>

      {startProcurement.error && (
        <p className="rounded-lg bg-rejected-dim px-3.5 py-2.5 text-sm text-rejected">
          {startProcurement.error.message}
        </p>
      )}

      <button
        type="submit"
        disabled={tooShort || isSubmitting}
        className={cn(
          "inline-flex w-full items-center justify-center gap-2 rounded-xl px-5 py-3",
          "text-sm font-semibold transition-all",
          "bg-rescue text-canvas hover:brightness-110",
          "disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:brightness-100",
        )}
      >
        {isSubmitting ? (
          <>
            <Loader2 className="size-4 animate-spin" aria-hidden />
            Dispatching agent…
          </>
        ) : (
          <>
            Dispatch buyer agent
            <ArrowRight className="size-4" aria-hidden />
          </>
        )}
      </button>
    </form>
  );
}
