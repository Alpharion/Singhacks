/**
 * The live buyer-agent client.
 *
 * Two endpoints, exactly as frozen in packages/contracts/openapi.yaml:
 *   POST /api/procure        -> 202 AgentRun   (Idempotency-Key required)
 *   GET  /api/runs/{runId}   -> 200 AgentRun
 *
 * Note the path is `{runId}` in camelCase. PROJECT_CONTEXT.md section 10 writes
 * it as `{run_id}`, but the OpenAPI document is authority #1 and says `runId`.
 */

import type { AgentRun, ApiError, ProcurementRequest } from "@/lib/contracts/types";
import { BUYER_AGENT_BASE_URL } from "./config";

/** An error carrying the contract's `ApiError` body when the server sent one. */
export class ContractError extends Error {
  readonly status: number;
  readonly body?: ApiError;

  constructor(status: number, message: string, body?: ApiError) {
    super(message);
    this.name = "ContractError";
    this.status = status;
    this.body = body;
  }
}

async function readError(response: Response): Promise<ContractError> {
  let body: ApiError | undefined;
  try {
    body = (await response.json()) as ApiError;
  } catch {
    // Non-JSON error body; fall through to the status text.
  }
  return new ContractError(
    response.status,
    body?.message ?? `${response.status} ${response.statusText}`,
    body,
  );
}

/**
 * The contract requires `Idempotency-Key` on POST /api/procure, matching
 * `^[A-Za-z0-9._:-]{8,128}$`. `randomUUID` satisfies that pattern.
 */
export function newIdempotencyKey(): string {
  return `procure-${crypto.randomUUID()}`;
}

export async function startProcurementLive(
  request: ProcurementRequest,
  idempotencyKey: string = newIdempotencyKey(),
): Promise<AgentRun> {
  const response = await fetch(`${BUYER_AGENT_BASE_URL}/api/procure`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "Idempotency-Key": idempotencyKey,
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) throw await readError(response);
  return (await response.json()) as AgentRun;
}

export async function getRunLive(runId: string): Promise<AgentRun> {
  const response = await fetch(
    `${BUYER_AGENT_BASE_URL}/api/runs/${encodeURIComponent(runId)}`,
    { headers: { accept: "application/json" } },
  );

  if (!response.ok) throw await readError(response);
  return (await response.json()) as AgentRun;
}
