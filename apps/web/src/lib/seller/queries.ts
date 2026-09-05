"use client";

/**
 * Reading and driving one listing.
 *
 * Unlike a buyer run, a listing is not something the agent finishes in a
 * moment: it stays open for the whole collection window and reprices on a tick,
 * so this polls until the window closes rather than revealing a finished run.
 * The price genuinely is changing while you watch it.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LISTING_POLL_INTERVAL_MS } from "@/lib/api/config";
import { createListing, getListing, recordDemand, recordSale } from "./client";
import { isTerminalListingStatus, type SellerListing } from "./types";

export function useListing(listingId: string) {
  const query = useQuery({
    queryKey: ["listing", listingId],
    queryFn: () => getListing(listingId),
    refetchInterval: (query) => {
      const listing = query.state.data;
      if (!listing || isTerminalListingStatus(listing.status)) return false;
      return LISTING_POLL_INTERVAL_MS;
    },
  });

  return {
    listing: query.data,
    isLoading: query.isPending,
    error: query.error as Error | null,
  };
}

export function useCreateListing() {
  return useMutation({
    mutationFn: ({ sellerId, requestText }: { sellerId: string; requestText: string }) =>
      createListing(sellerId, requestText),
  });
}

/** Shared cache update so a signal's result shows without waiting for the next poll. */
function useListingSignal(
  listingId: string,
  action: (listing: string, quantity: number) => Promise<SellerListing>,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (quantity: number) => action(listingId, quantity),
    onSuccess: (listing) => queryClient.setQueryData(["listing", listingId], listing),
  });
}

export function useRecordDemand(listingId: string) {
  return useListingSignal(listingId, recordDemand);
}

export function useRecordSale(listingId: string) {
  return useListingSignal(listingId, recordSale);
}
