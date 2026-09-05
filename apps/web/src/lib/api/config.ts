/**
 * Where the UI gets its data.
 *
 * `fixtures` replays the frozen contract fixtures in the browser - no backend
 * required, which is how the whole UI was built during Phase 1.
 * `live` talks to Person 2's buyer agent on port 8001.
 *
 * Integration is this one variable. Nothing else in the app changes.
 */

export type DataSource = "fixtures" | "live";

export const DATA_SOURCE: DataSource =
  process.env.NEXT_PUBLIC_DATA_SOURCE === "live" ? "live" : "fixtures";

export const BUYER_AGENT_BASE_URL =
  process.env.NEXT_PUBLIC_BUYER_AGENT_BASE_URL ?? "http://localhost:8001";

export const isFixtureMode = DATA_SOURCE === "fixtures";

/** How often to re-read a running run. The contract has no streaming endpoint. */
export const RUN_POLL_INTERVAL_MS = 1500;

/** How long each demo beat holds before the next one plays. */
export const DEMO_BEAT_INTERVAL_MS = 2200;
