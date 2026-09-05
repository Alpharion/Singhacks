/**
 * Where the UI gets its data.
 *
 * `live` talks to Person 2's buyer agent on port 8001. This is the default and
 * the demo path: the run on screen is one the agent actually performed.
 *
 * `fixtures` replays the frozen contract fixtures in the browser with a
 * playback clock and needs no backend. That is how the whole UI was built
 * during Phase 1, and it is kept as a development fallback - set
 * `NEXT_PUBLIC_DATA_SOURCE=fixtures` to get it back.
 *
 * Integration is this one variable. Nothing else in the app changes.
 */

export type DataSource = "fixtures" | "live";

export const DATA_SOURCE: DataSource =
  process.env.NEXT_PUBLIC_DATA_SOURCE === "fixtures" ? "fixtures" : "live";

/**
 * Base URL for the buyer agent, from the browser's point of view.
 *
 * Empty by default, which means "this origin" - requests go to `/api/...` and
 * `next.config.ts` rewrites them to the agent. Same-origin, so no CORS is
 * involved. Set `NEXT_PUBLIC_BUYER_AGENT_BASE_URL` to an absolute URL only if
 * you want the browser to call the agent directly, which requires the agent to
 * send CORS headers.
 */
export const BUYER_AGENT_BASE_URL = process.env.NEXT_PUBLIC_BUYER_AGENT_BASE_URL ?? "";

export const isFixtureMode = DATA_SOURCE === "fixtures";

/** How often to re-read a running run. The contract has no streaming endpoint. */
export const RUN_POLL_INTERVAL_MS = 1500;

/**
 * How often to re-read an open listing.
 *
 * Faster than the run poll because a listing's price is genuinely moving while
 * it is on screen, and a stale price is the one thing this view must not show.
 */
export const LISTING_POLL_INTERVAL_MS = 1000;

/** How long each demo beat holds before the next one plays. */
export const DEMO_BEAT_INTERVAL_MS = 2200;

/**
 * How long each event of a live run holds before the next is revealed.
 *
 * The agent finishes a simulated run in under a second, so without this the
 * dashboard jumps straight to the outcome and there is nothing to narrate. Set
 * `NEXT_PUBLIC_LIVE_REVEAL_MS=0` to disable the pacing and render each run the
 * instant it arrives.
 */
export const LIVE_REVEAL_INTERVAL_MS = Number(
  process.env.NEXT_PUBLIC_LIVE_REVEAL_MS ?? 900,
);
