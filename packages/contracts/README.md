# SurplusFlow Contract Freeze v1.0.0

Status: **FROZEN FOR PARALLEL IMPLEMENTATION**

Owner: Person 4

This package is the interface boundary between the frontend, buyer agent, marketplace, provider simulators, and XRPL payment adapter.

## Source of truth

1. `openapi.yaml` defines endpoints, headers, request bodies, responses, and HTTP status codes.
2. `schemas/*.schema.json` defines exact JSON fields and validation rules.
3. `fixtures/*.json` provides stable examples for independent development.
4. `contract-manifest.json` maps each fixture to the schema that validates it.

The x402 library owns the base64 wire payloads. SurplusFlow code must not create an alternative wire format. The application decodes and normalizes those payloads only for validation, persistence, and UI display.

## Frozen conventions

- JSON field names use `camelCase`.
- IDs are lowercase strings using letters, numbers, `_`, and `-`.
- Timestamps use ISO 8601 UTC strings.
- XRP amounts use integer strings in drops; never use floating-point XRP values.
- The MVP network is exactly `xrpl:1`.
- The MVP asset is exactly `XRP`.
- An `Idempotency-Key` header is required for every state-changing request.
- Provider payment retries reuse the same request body and idempotency key.
- The `Idempotency-Key` header must equal `PurchaseIntent.idempotencyKey`.
- x402 v2 headers are `PAYMENT-REQUIRED`, `PAYMENT-SIGNATURE`, and `PAYMENT-RESPONSE`.
- A provider returns useful value only after settlement is validated.
- Wallet seeds never appear in any request, response, fixture, log, or browser state.

The XRPL addresses and transaction hashes in fixtures are synthetic shape-valid examples, not funded accounts or evidence of settlement. Real Testnet values must come from ignored environment configuration and validated responses.

## Service and port ownership

| Service | Local port | Owner |
| --- | ---: | --- |
| Web UI | 3000 | Person 1 |
| Buyer agent | 8001 | Person 2 |
| Marketplace | 8002 | Person 3 |
| Green Oven seller | 8011 | Person 3 |
| Harbour Hotel seller | 8012 | Person 3 |
| Central Grill seller | 8013 | Person 3 |
| FastRoute courier | 8021 | Person 3 |
| Economy Van courier | 8022 | Person 3 |
| XRPL/x402 package | In-process adapter | Person 4 |

## Endpoint ownership

| Endpoint | Owner | Purpose |
| --- | --- | --- |
| `POST /api/procure` | Person 2 | Start an agent run |
| `GET /api/runs/{runId}` | Person 2 | Supply UI state and timeline |
| `GET /api/offers` | Person 3 | Free offer discovery |
| `POST /api/delivery/quotes` | Person 3 | Free courier discovery for a pickup set |
| `POST /api/sellers/{sellerId}/offers/{offerId}/reserve` | Person 3 + Person 4 adapter | Paid food reservation |
| `POST /api/delivery/{providerId}/book` | Person 3 + Person 4 adapter | Paid courier booking |
| `GET /api/reservations/{reservationId}` | Person 3 | Reservation status |
| `GET /api/transactions/{transactionHash}` | Person 4 | Normalized payment receipt |

## HTTP behavior

| Status | Meaning |
| ---: | --- |
| 200 | Read or search succeeded |
| 201 | Paid reservation or booking created |
| 202 | Procurement run accepted |
| 402 | Valid x402 payment challenge in `PAYMENT-REQUIRED` |
| 404 | Resource not found |
| 409 | Sold out, expired, duplicate, or state conflict |
| 422 | Request violates the contract |
| 503 | Provider unavailable; buyer agent may replan |

FastAPI's default validation body is not the public contract. Services must map validation failures to `ApiError` before responding.

## How each teammate starts

- Person 1 imports or copies types from the schemas and builds screens using `fixtures/agent-run.json`, `fixtures/food-offers.json`, and `fixtures/delivery-quotes.json`.
- Person 2 implements Pydantic v2 models matching the schemas and tests the state machine against all fixtures.
- Person 3 implements the documented provider endpoints and initially uses a payment-verification stub with the exact Person 4 adapter interface.
- Person 4 maintains this package, builds the x402 adapter, and rejects changes that do not update schemas and fixtures together.

## Validation

From this directory:

```text
pnpm install
pnpm test
```

`pnpm test` lints the OpenAPI document and validates every fixture against its JSON Schema.

## Change control

After freeze, a contract change requires:

1. A short request describing the blocked use case.
2. Person 4 approval.
3. Updates to OpenAPI, relevant schemas, fixtures, and tests in one change.
4. Notification to all three consumers.
5. A version bump: patch for clarifications, minor for backward-compatible additions, major for breaking changes.

Implementation-only changes that preserve the frozen wire shape do not require a contract version change.
