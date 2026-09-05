"use client";

/**
 * The one hook every screen uses to read a run.
 *
 * In fixture mode it projects the demo beat the playback clock is sitting on.
 * In live mode it polls `GET /api/runs/{runId}` until the run reaches a terminal
 * status. Callers cannot tell the difference - both return a `DemoSnapshot`.
 */

import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import type { AgentRun, ProcurementRequest } from "@/lib/contracts/types";
import { isTerminalStatus } from "@/lib/contracts/types";
import { RUN_POLL_INTERVAL_MS, isFixtureMode } from "@/lib/api/config";
import { getRunLive, startProcurementLive } from "@/lib/api/client";
import { usePlayback } from "@/lib/demo/playback";
import { projectRun, type DemoSnapshot } from "@/lib/demo/runProjection";
import { fixtureRun } from "@/lib/demo/fixtures";

export interface RunQueryResult {
  snapshot?: DemoSnapshot;
  isLoading: boolean;
  error: Error | null;
}

/** Wrap a live `AgentRun` in the same envelope the demo projection produces. */
function toSnapshot(run: AgentRun): DemoSnapshot {
  return { run, note: "" };
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

  const projected = useMemo(
    () => (isFixtureMode ? projectRun(step) : undefined),
    [step],
  );

  if (isFixtureMode) {
    return { snapshot: projected, isLoading: false, error: null };
  }

  return {
    snapshot: query.data ? toSnapshot(query.data) : undefined,
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
