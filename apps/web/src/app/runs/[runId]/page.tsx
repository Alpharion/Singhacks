import { RunDashboard } from "@/components/run/RunDashboard";

/**
 * `params` is a Promise in Next.js 16 and must be awaited before use.
 * The route segment is `runId` in camelCase, matching the contract's
 * `GET /api/runs/{runId}`.
 */
export default async function RunPage({ params }: PageProps<"/runs/[runId]">) {
  const { runId } = await params;
  return <RunDashboard runId={runId} />;
}
