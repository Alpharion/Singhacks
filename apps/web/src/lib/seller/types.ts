/**
 * Seller-agent types.
 *
 * Hand-written rather than generated: the seller agent is ours, and its shapes
 * are not part of Person 4's frozen buyer contract. They deliberately echo it -
 * a goal, a timeline, explained decisions, a terminal status - so a reader who
 * knows the buyer side already knows this one.
 *
 * Source of truth: services/seller-agent/src/seller_agent/models.py.
 */

import type { Drops } from "@/lib/contracts/types";

export type ListingStatus =
  | "queued"
  | "parsing"
  | "listed"
  | "repricing"
  | "cleared"
  | "expired"
  | "withdrawn";

export type ListingEventType =
  | "listing_parsed"
  | "listing_published"
  | "demand_observed"
  | "price_reduced"
  | "price_raised"
  | "price_held"
  | "floor_reached"
  | "units_sold"
  | "listing_cleared"
  | "listing_expired";

export type PricingAction = "open" | "reduce" | "raise" | "hold" | "floor";

export interface SellingGoal {
  goalId: string;
  sellerId: string;
  description: string;
  quantity: number;
  dietaryTags: string[];
  collectionDeadline: string;
  /** The price the agent may never go under. */
  floorUnitPriceDrops: Drops;
  openingUnitPriceDrops: Drops;
}

export interface PricingFactors {
  timeElapsed: number;
  sellThrough: number;
  pace: number;
  demand: number;
  enquiries: number;
  remaining: number;
}

export interface PricingDecision {
  decisionId: string;
  listingId: string;
  action: PricingAction;
  objective: string;
  previousUnitPriceDrops: Drops;
  unitPriceDrops: Drops;
  floorUnitPriceDrops: Drops;
  factors: PricingFactors;
  reasons: string[];
  rationale: string;
  createdAt: string;
}

export interface ListingEvent {
  sequence: number;
  eventType: ListingEventType;
  message: string;
  relatedId?: string;
  createdAt: string;
}

export interface ListingRevenue {
  unitsSold: number;
  grossDrops: Drops;
  floorValueDrops: Drops;
  /** Gross minus what the same units would have made at the floor. */
  upliftDrops: Drops;
}

export interface SellerListing {
  listingId: string;
  status: ListingStatus;
  goal: SellingGoal;
  unitPriceDrops: Drops;
  quantityRemaining: number;
  decisions: PricingDecision[];
  events: ListingEvent[];
  revenue: ListingRevenue;
  /** How much faster than wall-clock the agent's window runs. 1 is real time. */
  timeScale: number;
  /** True while buyers are simulated in-process rather than arriving for real. */
  simulatedMarket: boolean;
  createdAt: string;
  updatedAt: string;
}

export const TERMINAL_LISTING_STATUSES = ["cleared", "expired", "withdrawn"] as const;

export function isTerminalListingStatus(status: ListingStatus): boolean {
  return (TERMINAL_LISTING_STATUSES as readonly string[]).includes(status);
}
