/**
 * GENERATED FILE - DO NOT EDIT.
 *
 * Source: packages/contracts/openapi.yaml (Contract Freeze v1.0.0, owned by Person 4).
 * Regenerate with: pnpm sync:contracts
 *
 * Friendly aliases live in ./types.ts - import from there, not from this file.
 */
export interface paths {
    "/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Check service health */
        get: operations["getHealth"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/procure": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Start an autonomous procurement run */
        post: operations["startProcurement"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/runs/{runId}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read the latest agent state and timeline */
        get: operations["getProcurementRun"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/offers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Discover food offers without payment */
        get: operations["listFoodOffers"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/delivery/quotes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Get delivery quotes for a proposed set of pickups */
        post: operations["listDeliveryQuotes"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sellers/{sellerId}/offers/{offerId}/reserve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Purchase an exclusive food reservation
         * @description The first request normally returns HTTP 402 with a PAYMENT-REQUIRED
         *     header. The x402 buyer retries the same request with PAYMENT-SIGNATURE.
         *     The provider returns the reservation only after validated settlement.
         */
        post: operations["reserveFoodOffer"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/delivery/{providerId}/book": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Purchase a courier booking
         * @description Uses the same x402 challenge, settlement, and retry flow as food reservations.
         */
        post: operations["bookDelivery"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/reservations/{reservationId}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read a reservation */
        get: operations["getReservation"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/transactions/{transactionHash}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read a normalized validated XRPL settlement receipt */
        get: operations["getTransactionReceipt"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        Identifier: string;
        /** ProcurementRequest */
        "procurement-request.schema": {
            buyerId: components["schemas"]["Identifier"];
            requestText: string;
            walletPolicyId: components["schemas"]["Identifier"];
        };
        /** @enum {string} */
        RunStatus: "queued" | "parsing" | "discovering" | "planning" | "awaiting_payment" | "reserving" | "replanning" | "fulfilled" | "failed" | "cancelled";
        /** @enum {string} */
        DietaryTag: "vegetarian" | "vegan" | "halal" | "kosher" | "gluten_free" | "nut_free" | "dairy_free";
        Location: {
            zone: string;
            addressLine?: string;
            latitude?: number;
            longitude?: number;
        };
        PositiveDrops: string;
        /** ProcurementGoal */
        "procurement-goal.schema": {
            goalId: components["schemas"]["Identifier"];
            buyerId: components["schemas"]["Identifier"];
            mealCount: number;
            dietaryTags: components["schemas"]["DietaryTag"][];
            destination: components["schemas"]["Location"];
            /** Format: date-time */
            deliveryDeadline: string;
            maxTotalSpendDrops: components["schemas"]["PositiveDrops"];
            minSellerReliability: number;
            /** @enum {string} */
            optimizationPriority: "balanced" | "lowest_cost" | "highest_reliability" | "lowest_waste";
            walletPolicyId: components["schemas"]["Identifier"];
            approvedSellerIds?: components["schemas"]["Identifier"][];
            approvedCourierIds?: components["schemas"]["Identifier"][];
            /** Format: date-time */
            createdAt: string;
        };
        XrplAddress: string;
        TimeWindow: {
            /** Format: date-time */
            start: string;
            /** Format: date-time */
            end: string;
        };
        /** FoodOffer */
        "food-offer.schema": {
            offerId: components["schemas"]["Identifier"];
            sellerId: components["schemas"]["Identifier"];
            sellerName: string;
            /** Format: uri */
            reservationEndpoint: string;
            payTo: components["schemas"]["XrplAddress"];
            title: string;
            description?: string;
            dietaryTags: components["schemas"]["DietaryTag"][];
            quantityAvailable: number;
            unitPriceDrops: components["schemas"]["PositiveDrops"];
            location: components["schemas"]["Location"];
            /** Format: date-time */
            preparedAt: string;
            /** Format: date-time */
            expiresAt: string;
            pickupWindow: components["schemas"]["TimeWindow"];
            reliabilityScore: number;
            /** @enum {string} */
            status: "available" | "reserved" | "sold_out" | "expired" | "withdrawn";
            /** Format: date-time */
            updatedAt: string;
        };
        /** DeliveryQuote */
        "delivery-quote.schema": {
            quoteId: components["schemas"]["Identifier"];
            providerId: components["schemas"]["Identifier"];
            providerName: string;
            /** Format: uri */
            bookingEndpoint: string;
            payTo: components["schemas"]["XrplAddress"];
            pickupSellerIds: components["schemas"]["Identifier"][];
            destinationZone: string;
            capacityMeals: number;
            priceDrops: components["schemas"]["PositiveDrops"];
            /** Format: date-time */
            pickupEta: string;
            /** Format: date-time */
            deliveryEta: string;
            /** Format: date-time */
            validUntil: string;
            reliabilityScore: number;
            /** @enum {string} */
            status: "available" | "unavailable" | "expired";
        };
        /** @description Integer amount in XRP drops. One XRP equals 1,000,000 drops. */
        Drops: string;
        /** ProcurementPlan */
        "procurement-plan.schema": {
            planId: components["schemas"]["Identifier"];
            goalId: components["schemas"]["Identifier"];
            foodAllocations: {
                sellerId: components["schemas"]["Identifier"];
                offerId: components["schemas"]["Identifier"];
                quantity: number;
                unitPriceDrops: components["schemas"]["PositiveDrops"];
                lineTotalDrops: components["schemas"]["PositiveDrops"];
                reliabilityScore: number;
            }[];
            deliveryQuoteId: components["schemas"]["Identifier"];
            totalMeals: number;
            foodCostDrops: components["schemas"]["PositiveDrops"];
            deliveryCostDrops: components["schemas"]["Drops"];
            totalCostDrops: components["schemas"]["PositiveDrops"];
            /** Format: date-time */
            expectedDeliveryAt: string;
            /** Format: date-time */
            validUntil: string;
            riskScore: number;
            feasible: boolean;
            rejectionReasons: string[];
        };
        TransactionHash: string;
        /** AgentDecision */
        "agent-decision.schema": {
            decisionId: components["schemas"]["Identifier"];
            runId: components["schemas"]["Identifier"];
            /** @enum {string} */
            decisionType: "reject_offer" | "select_plan" | "authorize_payment" | "replan" | "stop";
            objective: string;
            selectedOptionId?: components["schemas"]["Identifier"];
            alternativesConsidered: components["schemas"]["Identifier"][];
            reasons: string[];
            rejectedAlternatives: {
                optionId: components["schemas"]["Identifier"];
                reasons: string[];
            }[];
            remainingBudgetDrops: components["schemas"]["Drops"];
            walletPolicyId: components["schemas"]["Identifier"];
            transactionHash?: components["schemas"]["TransactionHash"];
            /** Format: date-time */
            createdAt: string;
        };
        /** @constant */
        Network: "xrpl:1";
        /**
         * PaymentReceipt
         * @description Normalized validated settlement receipt derived from PAYMENT-RESPONSE.
         */
        "payment-receipt.schema": {
            /** @constant */
            success: true;
            transaction: components["schemas"]["TransactionHash"];
            network: components["schemas"]["Network"];
            payer: components["schemas"]["XrplAddress"];
            payee: components["schemas"]["XrplAddress"];
            amountDrops: components["schemas"]["PositiveDrops"];
            invoiceId: string;
            /** @constant */
            validated: true;
            /** Format: date-time */
            validatedAt: string;
            /** Format: uri */
            explorerUrl: string;
        };
        /** Reservation */
        "reservation.schema": {
            reservationId: components["schemas"]["Identifier"];
            runId: components["schemas"]["Identifier"];
            sellerId: components["schemas"]["Identifier"];
            offerId: components["schemas"]["Identifier"];
            quantity: number;
            /** @enum {string} */
            status: "confirmed" | "expired" | "cancelled" | "failed";
            pickupWindow: components["schemas"]["TimeWindow"];
            pickupToken?: string;
            paymentReceipt: components["schemas"]["payment-receipt.schema"];
            /** Format: date-time */
            createdAt: string;
            /** Format: date-time */
            expiresAt: string;
        };
        /** DeliveryBooking */
        "delivery-booking.schema": {
            bookingId: components["schemas"]["Identifier"];
            runId: components["schemas"]["Identifier"];
            providerId: components["schemas"]["Identifier"];
            quoteId: components["schemas"]["Identifier"];
            /** @enum {string} */
            status: "confirmed" | "collecting" | "in_transit" | "delivered" | "cancelled" | "failed";
            /** Format: date-time */
            pickupEta: string;
            /** Format: date-time */
            deliveryEta: string;
            trackingCode: string;
            paymentReceipt: components["schemas"]["payment-receipt.schema"];
            /** Format: date-time */
            createdAt: string;
        };
        /** ApiError */
        "api-error.schema": {
            /** @enum {string} */
            error: "invalid_request" | "not_found" | "offer_expired" | "offer_sold_out" | "quote_expired" | "provider_unavailable" | "budget_exceeded" | "policy_rejected" | "payment_required" | "payment_failed" | "payment_timeout" | "payment_replayed" | "invoice_mismatch" | "network_mismatch" | "internal_error";
            message: string;
            retryable: boolean;
            requestId: string;
            details?: {
                [key: string]: unknown;
            };
        };
        /** AgentRun */
        "agent-run.schema": {
            runId: components["schemas"]["Identifier"];
            status: components["schemas"]["RunStatus"];
            goal: components["schemas"]["procurement-goal.schema"];
            offers: components["schemas"]["food-offer.schema"][];
            deliveryQuotes: components["schemas"]["delivery-quote.schema"][];
            plans: components["schemas"]["procurement-plan.schema"][];
            selectedPlanId?: components["schemas"]["Identifier"];
            decisions: components["schemas"]["agent-decision.schema"][];
            reservations: components["schemas"]["reservation.schema"][];
            deliveryBookings: components["schemas"]["delivery-booking.schema"][];
            spend: {
                foodDrops: components["schemas"]["Drops"];
                deliveryDrops: components["schemas"]["Drops"];
                totalDrops: components["schemas"]["Drops"];
                remainingDrops: components["schemas"]["Drops"];
            };
            events: {
                sequence: number;
                /** @enum {string} */
                eventType: "goal_parsed" | "offers_discovered" | "offer_rejected" | "plans_built" | "plan_selected" | "provider_failed" | "replanning_started" | "payment_required" | "payment_authorized" | "payment_settled" | "reservation_confirmed" | "delivery_confirmed" | "run_fulfilled" | "run_failed";
                message: string;
                relatedId?: components["schemas"]["Identifier"];
                /** Format: date-time */
                createdAt: string;
            }[];
            failure?: components["schemas"]["api-error.schema"];
            /** Format: date-time */
            createdAt: string;
            /** Format: date-time */
            updatedAt: string;
        };
        /** FoodOffersResponse */
        "food-offers-response.schema": {
            offers: components["schemas"]["food-offer.schema"][];
            /** Format: date-time */
            generatedAt: string;
        };
        /** DeliveryQuoteRequest */
        "delivery-quote-request.schema": {
            goalId: components["schemas"]["Identifier"];
            pickups: {
                sellerId: components["schemas"]["Identifier"];
                offerId: components["schemas"]["Identifier"];
                quantity: number;
                location: components["schemas"]["Location"];
            }[];
            destination: components["schemas"]["Location"];
            /** Format: date-time */
            deliveryDeadline: string;
        };
        /** DeliveryQuotesResponse */
        "delivery-quotes-response.schema": {
            quotes: components["schemas"]["delivery-quote.schema"][];
            /** Format: date-time */
            generatedAt: string;
        };
        /** @enum {string} */
        ResourceType: "food_reservation" | "delivery_booking";
        /** @constant */
        Asset: "XRP";
        /**
         * PurchaseIntent
         * @description Validated application intent. It is not a signed XRPL transaction.
         */
        "purchase-intent.schema": {
            intentId: components["schemas"]["Identifier"];
            runId: components["schemas"]["Identifier"];
            goalId: components["schemas"]["Identifier"];
            resourceType: components["schemas"]["ResourceType"];
            providerId: components["schemas"]["Identifier"];
            resourceId: components["schemas"]["Identifier"];
            /** Format: uri */
            targetUrl: string;
            quantity?: number;
            amountDrops: components["schemas"]["PositiveDrops"];
            payTo: components["schemas"]["XrplAddress"];
            network: components["schemas"]["Network"];
            asset: components["schemas"]["Asset"];
            invoiceId: string;
            idempotencyKey: string;
            /** Format: date-time */
            expiresAt: string;
            rationale: string;
            policySnapshot: {
                walletPolicyId: components["schemas"]["Identifier"];
                maxOrderSpendDrops: components["schemas"]["PositiveDrops"];
                maxTransactionSpendDrops: components["schemas"]["PositiveDrops"];
                allowedPayees: components["schemas"]["XrplAddress"][];
            };
        };
    };
    responses: {
        /** @description An XRPL payment is required before the provider returns value. */
        PaymentRequired: {
            headers: {
                "PAYMENT-REQUIRED": components["headers"]["PaymentRequired"];
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["api-error.schema"];
            };
        };
        /** @description Request does not satisfy the frozen contract. */
        InvalidRequest: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["api-error.schema"];
            };
        };
        /** @description Requested resource does not exist. */
        NotFound: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["api-error.schema"];
            };
        };
        /** @description Resource state or idempotency conflict. */
        Conflict: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["api-error.schema"];
            };
        };
        /** @description Provider cannot fulfil the request; the agent may replan. */
        ProviderUnavailable: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["api-error.schema"];
            };
        };
    };
    parameters: {
        /** @description Stable key reused only when retrying the same logical request. */
        IdempotencyKey: string;
        /** @description Base64-encoded x402 v2 signed payment payload, generated by x402-xrpl. */
        PaymentSignature: string;
        RunId: components["schemas"]["Identifier"];
        SellerId: components["schemas"]["Identifier"];
        OfferId: components["schemas"]["Identifier"];
        ProviderId: components["schemas"]["Identifier"];
        ReservationId: components["schemas"]["Identifier"];
        TransactionHash: components["schemas"]["TransactionHash"];
    };
    requestBodies: never;
    headers: {
        /** @description Base64-encoded x402 v2 payment challenge. Decode to PaymentRequirement. */
        PaymentRequired: string;
        /** @description Base64-encoded x402 v2 settlement result. Decode and normalize to PaymentReceipt. */
        PaymentResponse: string;
    };
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    getHealth: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Service is healthy */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        /** @constant */
                        status: "ok";
                    };
                };
            };
        };
    };
    startProcurement: {
        parameters: {
            query?: never;
            header: {
                /** @description Stable key reused only when retrying the same logical request. */
                "Idempotency-Key": components["parameters"]["IdempotencyKey"];
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["procurement-request.schema"];
            };
        };
        responses: {
            /** @description Procurement run accepted */
            202: {
                headers: {
                    /** @description URL of the created run */
                    Location?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["agent-run.schema"];
                };
            };
            409: components["responses"]["Conflict"];
            422: components["responses"]["InvalidRequest"];
        };
    };
    getProcurementRun: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                runId: components["parameters"]["RunId"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Current procurement run */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["agent-run.schema"];
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    listFoodOffers: {
        parameters: {
            query?: {
                dietaryTag?: "vegetarian" | "vegan" | "halal" | "kosher" | "gluten_free" | "nut_free" | "dairy_free";
                availableAt?: string;
                minQuantity?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Available and recently unavailable offers */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["food-offers-response.schema"];
                };
            };
            422: components["responses"]["InvalidRequest"];
        };
    };
    listDeliveryQuotes: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["delivery-quote-request.schema"];
            };
        };
        responses: {
            /** @description Delivery quotes */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["delivery-quotes-response.schema"];
                };
            };
            422: components["responses"]["InvalidRequest"];
        };
    };
    reserveFoodOffer: {
        parameters: {
            query?: never;
            header: {
                /** @description Stable key reused only when retrying the same logical request. */
                "Idempotency-Key": components["parameters"]["IdempotencyKey"];
                /** @description Base64-encoded x402 v2 signed payment payload, generated by x402-xrpl. */
                "PAYMENT-SIGNATURE"?: components["parameters"]["PaymentSignature"];
            };
            path: {
                sellerId: components["parameters"]["SellerId"];
                offerId: components["parameters"]["OfferId"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["purchase-intent.schema"];
            };
        };
        responses: {
            /** @description Paid reservation created */
            201: {
                headers: {
                    "PAYMENT-RESPONSE": components["headers"]["PaymentResponse"];
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["reservation.schema"];
                };
            };
            402: components["responses"]["PaymentRequired"];
            409: components["responses"]["Conflict"];
            422: components["responses"]["InvalidRequest"];
            503: components["responses"]["ProviderUnavailable"];
        };
    };
    bookDelivery: {
        parameters: {
            query?: never;
            header: {
                /** @description Stable key reused only when retrying the same logical request. */
                "Idempotency-Key": components["parameters"]["IdempotencyKey"];
                /** @description Base64-encoded x402 v2 signed payment payload, generated by x402-xrpl. */
                "PAYMENT-SIGNATURE"?: components["parameters"]["PaymentSignature"];
            };
            path: {
                providerId: components["parameters"]["ProviderId"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["purchase-intent.schema"];
            };
        };
        responses: {
            /** @description Paid delivery booking created */
            201: {
                headers: {
                    "PAYMENT-RESPONSE": components["headers"]["PaymentResponse"];
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["delivery-booking.schema"];
                };
            };
            402: components["responses"]["PaymentRequired"];
            409: components["responses"]["Conflict"];
            422: components["responses"]["InvalidRequest"];
            503: components["responses"]["ProviderUnavailable"];
        };
    };
    getReservation: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                reservationId: components["parameters"]["ReservationId"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Reservation state */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["reservation.schema"];
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    getTransactionReceipt: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                transactionHash: components["parameters"]["TransactionHash"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Validated payment receipt */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["payment-receipt.schema"];
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
}
