"use client";

/**
 * The one hook every screen uses to read a run.
 *
 * In fixture mode it projects the demo beat the playback clock is sitting on.
 * In live mode it polls `GET /api/runs/{runId}` until the run reaches a terminal
 * status. Callers cannot tell the difference - both return a `DemoSnapshot`.
 */

import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import type { ProcurementRequest } from "@/lib/contracts/types";
import { isTerminalStatus } from "@/lib/contracts/types";
import type { AgentRun } from "@/lib/contracts/types";
import {
  LIVE_REVEAL_INTERVAL_MS,
  RUN_POLL_INTERVAL_MS,
  isFixtureMode,
} from "@/lib/api/config";
import { getRunLive, startProcurementLive } from "@/lib/api/client";
import { usePlayback } from "@/lib/demo/playback";
import { projectRun, type DemoSnapshot } from "@/lib/demo/runProjection";
import { revealRun } from "@/lib/demo/liveReveal";
import { fixtureRun } from "@/lib/demo/fixtures";

export interface RunQueryResult {
  snapshot?: DemoSnapshot;
  isLoading: boolean;
  error: Error | null;
}

export function useRun(runId: string): RunQueryResult {
  const playback = usePlayback();
  const step = playback?.step ?? 0;

  const query = useQuery({
    queryKey: ["run", runId],
    queryFn: () => getRunLive(runId),
    enabled: !isFixtureMode,
    refetchInterval: (query) => {
      const run = query.state.data;
      if (!run || isTerminalStatus(run.status)) return false;
      return RUN_POLL_INTERVAL_MS;
    },
  });

  // How many of the live run's events have been shown. The agent finishes far
  // faster than a person can read, so events are released on a timer; see
  // `revealRun`, which only decides *when* real data appears, never what.
  //
  // The run id is stored alongside the count so a different run starts from the
  // beginning without needing an effect to reset it - a stale entry simply does
  // not match and reads as zero.
  const [progress, setProgress] = useState({ runId, count: 0 });
  const liveRun: AgentRun | undefined = query.data;
  const eventCount = liveRun?.events.length ?? 0;

  const paced = LIVE_REVEAL_INTERVAL_MS > 0;
  const revealed = paced ? (progress.runId === runId ? progress.count : 0) : eventCount;

  useEffect(() => {
    if (isFixtureMode || !paced || revealed >= eventCount) return;
    const timer = setTimeout(
      () => setProgress({ runId, count: revealed + 1 }),
      // The first beat lands immediately so the page is never blank.
      revealed === 0 ? 0 : LIVE_REVEAL_INTERVAL_MS,
    );
    return () => clearTimeout(timer);
  }, [runId, paced, revealed, eventCount]);

  const projected = useMemo(
    () => (isFixtureMode ? projectRun(step) : undefined),
    [step],
  );

  const revealedSnapshot = useMemo(
    () => (liveRun ? revealRun(liveRun, revealed) : undefined),
    [liveRun, revealed],
  );

  if (isFixtureMode) {
    return { snapshot: projected, isLoading: false, error: null };
  }

  return {
    snapshot: revealedSnapshot,
    isLoading: query.isPending,
    error: query.error,
  };
}

/**
 * Start a run. In fixture mode this resolves immediately to the demo run id so
 * the form still navigates; the playback clock then tells the story.
 */
export function useStartProcurement() {
  return useMutation({
    mutationFn: async (request: ProcurementRequest): Promise<AgentRun> => {
      if (isFixtureMode) return fixtureRun;
      return startProcurementLive(request);
    },
  });
}
