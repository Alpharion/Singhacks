/**
 * Typed access to the copied contract fixtures.
 *
 * `resolveJsonModule` widens every literal to `string`, so a raw JSON import
 * gives `status: string` rather than `status: RunStatus`. Each fixture is cast
 * once here, and nothing else in the app imports the JSON directly.
 *
 * These files are byte-identical copies of packages/contracts/fixtures.
 * Their XRPL addresses and transaction hashes are synthetic placeholders.
 */

import type {
  AgentRun,
  DeliveryQuotesResponse,
  FoodOffersResponse,
  PaymentRequirement,
  ProcurementRequest,
  PurchaseIntent,
  ApiError,
} from "@/lib/contracts/types";

import agentRunJson from "./fixtures/agent-run.json";
import deliveryQuotesJson from "./fixtures/delivery-quotes.json";
import foodOffersJson from "./fixtures/food-offers.json";
import paymentRequirementJson from "./fixtures/payment-requirement.json";
import procurementRequestJson from "./fixtures/procurement-request.json";
import providerFailureJson from "./fixtures/provider-failure.json";
import purchaseIntentJson from "./fixtures/purchase-intent.json";

export const fixtureRun = agentRunJson as AgentRun;
export const fixtureOffers = (foodOffersJson as FoodOffersResponse).offers;
export const fixtureQuotes = (deliveryQuotesJson as DeliveryQuotesResponse).quotes;
export const fixturePaymentRequirement = paymentRequirementJson as PaymentRequirement;
export const fixtureProcurementRequest = procurementRequestJson as ProcurementRequest;
export const fixtureProviderFailure = providerFailureJson as ApiError;
export const fixturePurchaseIntent = purchaseIntentJson as PurchaseIntent;

/**
 * The spending limits the human delegated. Lives on `PurchaseIntent`, which the
 * browser never sees in live mode - it is the payment boundary's record, shown
 * here so the demo can make the delegated authority explicit.
 */
export const demoPolicy = fixturePurchaseIntent.policySnapshot;

/**
 * The run fixture ships with `offers: []` and `deliveryQuotes: []` even though
 * its plans reference `offer_bakery_001` and friends. Anything that needs to
 * resolve an id to a seller name has to look here instead of at `run.offers`.
 */
export const offersById = new Map(fixtureOffers.map((offer) => [offer.offerId, offer]));
export const quotesById = new Map(fixtureQuotes.map((quote) => [quote.quoteId, quote]));
