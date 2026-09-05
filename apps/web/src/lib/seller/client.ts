/**
 * The seller-agent client.
 *
 * Same shape as the buyer client, and same proxy arrangement: the browser calls
 * `/api/seller/...` on this origin and `next.config.ts` forwards it to the
 * seller agent on :8003, so nothing here is cross-origin.
 */

import { ContractError } from "@/lib/api/client";
import type { SellerListing } from "./types";

async function readError(response: Response): Promise<ContractError> {
  let body: { error?: string; message?: string } | undefined;
  try {
    body = await response.json();
  } catch {
    // Non-JSON body; fall through to the status text.
  }
  return new ContractError(
    response.status,
    body?.message ?? `${response.status} ${response.statusText}`,
  );
}

export function newListingKey(): string {
  return `listing-${crypto.randomUUID()}`;
}

export async function createListing(
  sellerId: string,
  requestText: string,
  idempotencyKey: string = newListingKey(),
): Promise<SellerListing> {
  const response = await fetch("/api/seller/listings", {
    method: "POST",
    headers: { "content-type": "application/json", "Idempotency-Key": idempotencyKey },
    body: JSON.stringify({ sellerId, requestText }),
  });
  if (!response.ok) throw await readError(response);
  return (await response.json()) as SellerListing;
}

export async function getListing(listingId: string): Promise<SellerListing> {
  const response = await fetch(
    `/api/seller/listings/${encodeURIComponent(listingId)}`,
    { headers: { accept: "application/json" } },
  );
  if (!response.ok) throw await readError(response);
  return (await response.json()) as SellerListing;
}

/**
 * Tell the agent a buyer is interested.
 *
 * In a joined-up stack the buyer agent's discovery call would raise this; the
 * demo exposes it as a button so the effect of demand on price can be shown
 * rather than described.
 */
export async function recordDemand(
  listingId: string,
  quantity = 20,
): Promise<SellerListing> {
  const response = await fetch(
    `/api/seller/listings/${encodeURIComponent(listingId)}/demand`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ quantity, source: "buyer_agent" }),
    },
  );
  if (!response.ok) throw await readError(response);
  return (await response.json()) as SellerListing;
}

export async function recordSale(
  listingId: string,
  quantity: number,
): Promise<SellerListing> {
  const response = await fetch(
    `/api/seller/listings/${encodeURIComponent(listingId)}/sale`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ quantity }),
    },
  );
  if (!response.ok) throw await readError(response);
  return (await response.json()) as SellerListing;
}
