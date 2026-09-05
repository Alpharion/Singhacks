"use client";

import { Loader2 } from "lucide-react";
import { useRun } from "@/lib/queries";
import { Panel } from "@/components/common/Panel";
import { RunHeader } from "./RunHeader";
import { PlaybackControls } from "./PlaybackControls";
import { AgentTimeline } from "./AgentTimeline";
import { OfferTable } from "./OfferTable";
import { PlanComparison } from "./PlanComparison";
import { DecisionList } from "./DecisionCard";
import { PaymentPanel } from "./PaymentPanel";
import { FulfilmentPanel } from "./FulfilmentPanel";
import { SpendChart } from "./SpendChart";
import { OutcomeSummary } from "./OutcomeSummary";
import { FailureBanner } from "./FailureBanner";

/**
 * Mission control.
 *
 * Reads one run through `useRun`, which hides whether the data is a replayed
 * fixture or a live poll of the buyer agent. Every panel below is a pure
 * function of that run.
 */
export function RunDashboard({ runId }: { runId: string }) {
  const { snapshot, isLoading, error } = useRun(runId);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center gap-2.5 py-24 text-sm text-ink-muted">
        <Loader2 className="size-4 animate-spin" aria-hidden />
        Loading run {runId}…
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-lg py-24 text-center">
        <p className="text-sm font-medium text-rejected">Could not load run {runId}</p>
        <p className="mt-1.5 text-sm text-ink-muted">{error.message}</p>
      </div>
    );
  }

  if (!snapshot) return null;

  const { run, paymentChallenge, note } = snapshot;

  return (
    <div className="mx-auto max-w-[1400px] space-y-4 px-6 py-6">
      <RunHeader run={run} />
      <PlaybackControls note={note} />

      {run.failure && <FailureBanner failure={run.failure} />}
      <OutcomeSummary run={run} />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
        {/* Left rail: what the agent did, in order. */}
        <div className="space-y-4">
          <Panel title="Agent activity" subtitle="Live decision timeline">
            <AgentTimeline events={run.events} />
          </Panel>

          <Panel title="Budget" subtitle="Delegated authority against actual spend">
            <SpendChart run={run} />
          </Panel>
        </div>

        {/* Right: the evidence behind each step. */}
        <div className="space-y-4">
          <Panel
            title="Discovery"
            subtitle="Offers and quotes the agent considered, and what it turned down"
          >
            <OfferTable run={run} />
          </Panel>

          <Panel title="Plans compared" subtitle="Multi-seller combinations, ranked">
            <PlanComparison run={run} />
          </Panel>

          <Panel title="Decisions" subtitle="Why each choice was made, and what was rejected">
            <DecisionList decisions={run.decisions} />
          </Panel>

          <Panel title="Payments" subtitle="x402 challenges and validated XRPL settlement">
            <PaymentPanel run={run} challenge={paymentChallenge} />
          </Panel>

          <Panel title="Value delivered" subtitle="What the payments actually bought">
            <FulfilmentPanel run={run} />
          </Panel>
        </div>
      </div>
    </div>
  );
}
