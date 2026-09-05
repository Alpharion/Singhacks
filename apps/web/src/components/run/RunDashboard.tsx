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
import { SettlementNotice } from "./SettlementNotice";

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

      <SettlementNotice run={run} />
      {run.failure && <FailureBanner failure={run.failure} />}
      <OutcomeSummary run={run} />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
        {/* Left rail: what the agent did, in order. */}
        <div className="space-y-4">
          <Panel title="What the agent is doing" subtitle="Every step, as it happens">
            <AgentTimeline events={run.events} />
          </Panel>

          <Panel title="Where the money went" subtitle="Against the ceiling you set">
            <SpendChart run={run} />
          </Panel>
        </div>

        {/* Right: the evidence behind each step. */}
        <div className="space-y-4">
          <Panel
            title="What's on the shelf"
            subtitle="Everything the agent found, and what it turned down"
          >
            <OfferTable run={run} />
          </Panel>

          <Panel title="Ways to fill the order" subtitle="No single kitchen has 100 meals, so it combines them">
            <PlanComparison run={run} />
          </Panel>

          <Panel title="Why it chose what it chose" subtitle="Each call, with the alternatives it passed on">
            <DecisionList decisions={run.decisions} />
          </Panel>

          <Panel title="Payments" subtitle="Asked for payment over x402, settled on XRPL">
            <PaymentPanel run={run} challenge={paymentChallenge} />
          </Panel>

          <Panel title="Food secured" subtitle="What the money actually bought">
            <FulfilmentPanel run={run} />
          </Panel>
        </div>
      </div>
    </div>
  );
}
