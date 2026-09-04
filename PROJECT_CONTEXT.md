# SurplusFlow - Standalone Project Context

This document is intended to be pasted into a new AI chat so that the AI can understand the hackathon, product, architecture, fixed technology stack, implementation boundaries, and four-person ownership plan without needing the previous conversation.

> **Contract Freeze v1.0.0 is active.** This document freezes product scope, ownership, naming, and interface policy. The machine-readable source of truth is `packages/contracts/openapi.yaml` together with `packages/contracts/schemas/`. Fixtures in `packages/contracts/fixtures/` are the approved examples for parallel development. Contract changes must be requested through Person 4 and released as a new contract version.

## 1. Hackathon Context

The Ripple SingHacks challenge asks teams to design an AI-native product or service that solves a real customer problem and demonstrates how autonomous agentic payments enable a new or significantly better business experience.

The challenge's north star is:

> Do not merely make an AI agent send a transaction. Build a business that works because an AI agent can discover, decide, transact, and deliver value.

A strong submission must demonstrate a complete commercial loop:

```text
Customer need
    -> AI understands the objective, budget, and constraints
    -> AI discovers or compares providers
    -> AI makes an economic decision
    -> AI initiates a payment
    -> XRPL settles the transaction
    -> A useful product, service, or outcome is delivered
```

### Hard technical requirements

- All blockchain activity must use the XRP Ledger (XRPL).
- The XRPL EVM Sidechain and other blockchains do not count.
- The prototype must execute at least one successful XRPL transaction.
- The final submission must include the validated transaction hash or explorer link.

### Recommended technology

- XRPL AI Starter Kit or its agent wallet/payment patterns
- An agentic payment standard such as x402 or MPP
- XRPL Testnet during development

x402, MPP, and the Starter Kit are recommended rather than hard requirements in the current repository instructions. SurplusFlow will nevertheless use x402 because it makes the machine-to-machine commercial loop explicit.

The XRPL AI Starter Kit is a curated collection of agent-payment tools, documentation, wallet/payment skills, and integrations rather than a single application framework that the whole product must import. SurplusFlow uses its intended build path through:

- XRPL agent wallet and payment safety patterns
- XRPL documentation and transaction tooling
- x402 payments using XRP on XRPL
- Transaction confirmation and attribution through hashes, invoice IDs, and source tags

The project must describe these concrete integrations in the submission; it must not claim that an unspecified package called "the Starter Kit" powers the application.

### Product requirements

- Clear customer problem and target user
- Clear product proposition
- Meaningful AI role
- Provider discovery or comparison
- Autonomous or user-authorized economic decision
- Spending constraints and authorization boundaries
- XRPL settlement
- Useful value returned after payment
- Credible commercial model
- Failure handling, traceability, and safeguards

### Judging criteria

| Category | Weight | What SurplusFlow must demonstrate |
| --- | ---: | --- |
| Reachability | 20% | A model that can expand across food providers, bulk buyers, and cities |
| Creativity | 20% | Agents autonomously trading time-sensitive surplus rather than a normal marketplace checkout |
| Feasibility | 20% | Realistic inventory, reservation, payment, expiry, refund, and delivery behavior |
| Technical depth | 20% | AI reasoning, x402, XRPL settlement, wallet controls, testing, and failure recovery |
| UX and design | 10% | A clear request-to-fulfilment journey with understandable agent decisions and transactions |
| Builder feedback | 10% | Continuous feedback hook plus the final builder-feedback form |

### Submission requirements

- Public GitHub repository
- Source code and reproducible setup instructions
- Product overview and customer problem
- Architecture diagram
- Explanation of AI-agent behavior
- Explanation of x402 and XRPL integration
- At least one successful XRPL transaction hash or explorer reference
- Working end-to-end prototype
- Builder feedback completed

The repository contains a project-specific feedback hook. Before implementation, the team must read `agent-instruction.md` and `hook/INSTALL.md`, configure the real team and participant names, register the hook at project scope, and verify that it works. Do not invent those names.

## 2. Meaning of Agentic Payment

An agentic payment is not just a transaction initiated by software. It results from an AI agent making a contextual economic decision within authority delegated by a user.

Weak example:

```text
Human chooses Bakery A and the exact amount.
Software sends the payment.
```

Strong example:

```text
The buyer authorizes up to 120 XRP for 100 vegetarian meals before 6 PM.
The agent discovers several sellers and couriers.
It compares price, quantity, expiry, distance, reliability, and delivery cost.
It decides which combination to purchase and whom to pay.
It pays those providers and returns confirmed reservations and delivery.
```

The user defines the objective and boundaries. The agent decides the individual economic actions inside those boundaries.

## 3. Product Summary

### Product name

SurplusFlow

### One-sentence proposition

SurplusFlow helps community kitchens acquire affordable meals from fragmented, expiring food inventory by allowing an AI buyer agent to discover the best combination of surplus food, pay sellers and couriers through x402 on XRPL, and return a confirmed fulfilment plan before the food becomes waste.

### Customer problem

Community kitchens, food banks, charities, caterers, and institutional canteens often need affordable meals in bulk under strict quantity, dietary, budget, and delivery constraints. Suitable surplus exists across bakeries, restaurants, supermarkets, hotels, and caterers, but it is fragmented, changes quickly, and expires.

A procurement manager cannot continuously monitor many providers, calculate multi-seller combinations, compare delivery routes, and approve several time-sensitive payments before another buyer takes the inventory.

Food providers have the opposite problem: staff are too busy to repeatedly identify, list, price, update, and coordinate surplus food before it must be discarded.

### Primary target user

For the MVP, the primary customer is:

> A community-kitchen procurement manager who needs to acquire 50-200 safe meals each day within a strict budget, dietary policy, location, and delivery deadline.

### Secondary users

Food sellers:

- Bakeries
- Restaurants and cafes
- Hotels
- Supermarkets
- Caterers
- Food manufacturers

Delivery providers:

- Local couriers
- Cold-chain delivery services
- Volunteer delivery networks

### Business model

- Percentage fee on successfully reserved surplus-food orders
- Delivery coordination fee
- Subscription for high-volume food providers
- Sustainability and waste-reduction reporting for enterprise sellers

For the hackathon MVP, platform-fee settlement is not part of the critical path. The core paid actions are food reservation and courier booking.

## 4. MVP Scenario

The live demonstration uses this request:

> Acquire 100 vegetarian meals for a community kitchen, deliver them by 6 PM, and spend no more than 120 XRP including delivery.

The prototype contains:

- One community-kitchen buyer
- One genuine AI buyer agent
- Three simulated food-provider services
- Two simulated courier-provider services
- Different prices, quantities, expiry times, locations, and reliability scores
- One seller that becomes unavailable after the initial plan
- x402-protected reservation and courier-booking endpoints
- Real XRPL Testnet payments
- Post-payment reservation tokens and delivery confirmation
- A dashboard showing decisions, rejected alternatives, spending, and transaction hashes

The MVP is not a full consumer marketplace. It is a focused demonstration of autonomous multi-provider procurement.

## 5. Agent Roles

### Buyer agent - primary AI capability

The buyer agent represents the community kitchen.

It receives:

- Required meal quantity
- Dietary constraints
- Maximum total budget
- Delivery address or zone
- Required arrival time
- Minimum seller reliability
- Approved provider policy
- Wallet authorization policy

It performs:

1. Natural-language objective parsing into a typed `ProcurementGoal`.
2. Discovery of food offers and courier quotes.
3. Hard filtering of expired, unsafe, incompatible, or unauthorized offers.
4. Generation of feasible multi-seller combinations.
5. Calculation of total food and delivery cost.
6. Ranking based on price, reliability, distance, expiry risk, and deadline.
7. Selection of the best valid plan.
8. Explanation of selected and rejected alternatives.
9. Payment authorization within the user's fixed policy.
10. Reservation and courier booking.
11. Validation of returned receipts and transaction hashes.
12. Replanning when a seller, payment, or courier fails.
13. Stopping once the requested quantity is secured or no valid plan remains.

The LLM must not directly construct or sign transactions. It produces structured purchase intents. Deterministic policy and payment code validates and executes those intents.

### Seller services

Each seller service represents a bakery, restaurant, hotel, or supermarket. A seller may eventually use AI for demand prediction and dynamic pricing, but the hackathon only requires the buyer agent to be genuinely intelligent.

Seller services:

- Publish free, machine-readable offer metadata.
- Enforce food-safety and expiry rules deterministically.
- Adjust prices within configured minimum and maximum boundaries.
- Return HTTP 402 payment requirements for reservation requests.
- Verify validated XRPL settlement through the facilitator.
- Lock paid inventory and prevent duplicate sale.
- Return a reservation ID, pickup window, and QR payload after payment.
- Remove expired or unavailable offers.
- Return explicit failure states for sold-out or payment-conflict cases.

Food-safety decisions are hard rules, not LLM discretion.

### Courier services

Courier services:

- Publish free quotes containing price, capacity, route, and ETA.
- Return HTTP 402 for a confirmed booking.
- Return a delivery booking ID and tracking status after payment.
- Simulate one capacity or route failure for fallback testing.

### Platform service

The marketplace service is infrastructure rather than an autonomous economic agent. It:

- Aggregates offer discovery.
- Stores public offer metadata and private reservation records.
- Tracks provider reputation and availability.
- Provides the buyer agent with provider endpoints.
- Does not choose purchases or hold buyer wallet secrets.

## 6. AI Design

Use a hybrid system rather than allowing an LLM to control the entire workflow.

### LLM responsibilities

- Parse a natural-language procurement request.
- Identify soft priorities such as cheapest, most reliable, or lowest waste.
- Produce structured constraints through Pydantic schemas.
- Explain why a plan was chosen.
- Explain failures and fallback behavior in plain language.

### Deterministic code responsibilities

- Dietary and expiry filtering
- Quantity calculations
- Combination generation
- Price and delivery calculations
- Spending-policy enforcement
- Provider allowlisting
- Invoice uniqueness and idempotency
- Payment construction and signing
- Stopping conditions

For three sellers, use Python's standard-library `itertools` to enumerate valid combinations. Do not introduce an optimization framework for the MVP.

### Required agent tools

The buyer agent may call only these typed tools:

```text
list_food_offers(goal)
list_delivery_quotes(pickups, destination, deadline)
build_procurement_plans(goal, offers, delivery_quotes)
reserve_offer(offer_id, purchase_intent)
book_delivery(quote_id, purchase_intent)
get_reservation_status(reservation_id)
get_transaction_status(transaction_hash)
```

### Required explanations

Every purchase must produce an `AgentDecision` containing:

- Objective being satisfied
- Alternatives considered
- Selected provider
- Selected amount
- Reasons for selection
- Reasons alternatives were rejected
- Remaining budget
- Applicable authorization policy
- Resulting transaction hash when available

## 7. XRPL and x402 Integration

### Responsibility split

```text
x402: communicates the price and payment requirements over HTTP
Buyer agent: decides whether the purchase is worthwhile
Policy layer: confirms the purchase is authorized
Buyer wallet: signs the payment locally
XRPL: validates and settles the payment
Seller or courier: returns the purchased reservation or booking
```

### Payment sequence

1. Offer and quote discovery endpoints are free.
2. The buyer calls a selected provider's reservation or booking endpoint.
3. The provider responds with HTTP 402 and XRPL payment requirements.
4. The buyer verifies the network, asset, amount, recipient, invoice, expiry, and spending policy.
5. The buyer signs a standard XRPL `Payment` transaction locally.
6. The x402 facilitator verifies and settles it on XRPL Testnet.
7. The client retries the request with payment proof.
8. The provider returns the reservation or booking.
9. The dashboard displays the validated transaction hash.

### MVP currency and network

- Network: XRPL Testnet (`xrpl:1`)
- Currency: XRP, denominated in drops inside transactions
- Display unit: XRP
- Facilitator: hosted XRPL Testnet x402 facilitator

Use XRP for the MVP because it avoids RLUSD trust-line and issuer configuration. RLUSD is a post-MVP enhancement for stable commercial pricing.

### Payment libraries

- `xrpl-py`
- `x402-xrpl`
- `requests`
- `python-dotenv`

Seller and courier services use the `x402_xrpl.server.require_payment` FastAPI middleware pattern. The buyer uses `x402_xrpl.clients.x402_requests` with an `xrpl:1` network filter.

### Required payment controls

- Default to Testnet.
- Never expose seeds in code, logs, UI, commits, prompts, or API responses.
- Load secrets only from ignored environment files.
- Sign locally.
- Cap total order spend.
- Cap spend per transaction.
- Allow only configured seller and courier addresses.
- Require unique invoice identifiers.
- Reject expired payment requirements.
- Prevent duplicate payment and reservation processing.
- Persist the transaction hash before or during submission recovery handling.
- Wait for validated settlement before returning the purchased resource.
- Keep private food, buyer, address, and dietary data off-chain.
- Put only an opaque invoice reference and agent attribution metadata on-chain.

### No escrow in the MVP

Do not use XRPL escrow in the core x402 flow. The current XRPL x402 Exact scheme expects a standard `Payment` transaction. Adding escrow would increase implementation and fulfilment-dispute complexity without improving the hackathon demonstration.

The paid product is a short-lived exclusive reservation or delivery booking. A production version can use a small reservation deposit followed by final settlement at pickup and explicit refund handling.

## 8. Fixed Technology Stack

Do not change this stack unless the team explicitly agrees to a project-wide migration.

### Frontend

- Node.js 20+
- Next.js 16 with App Router
- TypeScript 5 with strict mode
- React 19
- Tailwind CSS 4
- shadcn/ui components
- TanStack Query for server state
- Recharts for spending and fulfilment charts
- `react-qr-code` for pickup tokens

### Backend and provider APIs

- Python 3.11+
- FastAPI
- Uvicorn
- Pydantic v2
- SQLAlchemy 2
- SQLite for the hackathon MVP
- `httpx` for ordinary asynchronous service calls
- `requests` for the documented x402 buyer client wrapper

SQLite belongs only to the marketplace/provider backend. Other services access it through HTTP and must not open the database file directly.

### AI agent

- Python 3.11+
- OpenAI Responses API
- OpenAI Python SDK
- Pydantic structured outputs
- Deterministic optimizer written with Python standard-library functions
- Model selected through `OPENAI_MODEL`; do not hardcode a model name in business logic

Do not add LangChain, LangGraph, or another agent framework for the MVP. A small explicit state machine is easier to test and explain.

### Payments

- XRPL Testnet
- XRP for the MVP
- `xrpl-py`
- `x402-xrpl`
- Hosted XRPL Testnet facilitator
- Separate buyer, seller, and courier Testnet wallets

### Testing

- `pytest` for Python unit and integration tests
- FastAPI `TestClient` for API tests
- Vitest and React Testing Library for frontend components
- Playwright for one end-to-end demo path

### Local development

- `uv` for Python environments and dependency installation
- `pnpm` 9+ for the frontend
- Docker Compose for running all local services
- `.env.example` documents variables without secret values

### Deliberately excluded stack choices

- Do not use Solidity, an EVM chain, or the XRPL EVM Sidechain.
- Do not use both x402 and MPP in the MVP; x402 is the selected machine-payment protocol.
- Do not introduce a browser wallet for autonomous payments; the buyer agent uses a dedicated Testnet wallet held by the backend payment boundary.
- Do not let the frontend, LLM, marketplace, or provider services access the buyer wallet seed.
- Do not add PostgreSQL, Redis, Kafka, Kubernetes, or a vector database for the hackathon MVP.

## 9. Repository Structure

```text
ripple-SingHacks/
|-- apps/
|   `-- web/                         # Next.js frontend
|-- services/
|   |-- buyer-agent/                 # AI state machine and planner
|   |-- marketplace/                 # Offers, reservations, SQLite ownership
|   `-- providers/
|       |-- sellers/                 # Configurable seller simulators
|       `-- delivery/                # Configurable courier simulators
|-- packages/
|   |-- contracts/                   # OpenAPI and shared JSON schemas
|   `-- payments/                    # XRPL wallet and x402 wrappers
|-- tests/
|   `-- e2e/                         # Full demo path
|-- docs/
|   |-- architecture/
|   `-- demo/
|-- docker-compose.yml
|-- Makefile
|-- .env.example
|-- PROJECT_CONTEXT.md
`-- README.md
```

Each Python service owns its own `pyproject.toml`. The frontend owns its own `package.json`. This prevents contributors from frequently editing a shared dependency file.

## 10. API Contracts

Person 4 owns and freezes the OpenAPI/JSON schemas for:

```text
ProcurementGoal
FoodOffer
DeliveryQuote
ProcurementPlan
PlanSelection
PurchaseIntent
AgentDecision
PaymentRequirement
PaymentReceipt
Reservation
DeliveryBooking
```

Minimum endpoints:

```text
POST /api/procure
GET  /api/runs/{run_id}
GET  /api/offers
POST /api/delivery/quotes
POST /api/sellers/{seller_id}/offers/{offer_id}/reserve
POST /api/delivery/{provider_id}/book
GET  /api/reservations/{reservation_id}
GET  /api/transactions/{transaction_hash}
```

The frontend and services communicate only through these contracts. They must not import another contributor's internal source files.

### Frozen contract authority

The prose in this document explains intent. If field names, required values, response codes, or endpoint details are unclear, the following order of authority applies:

1. `packages/contracts/openapi.yaml`
2. `packages/contracts/schemas/*.schema.json`
3. `packages/contracts/fixtures/*.json`
4. This prose document

Do not change an interface silently. Person 4 must update the OpenAPI file, affected schemas, fixtures, contract version, and validation checks together.

## 11. Four-Person Parallel Work Plan

### Person 1 - Frontend, UX, and submission narrative

Exclusive ownership:

```text
apps/web/**
docs/demo/**
README.md
```

Responsibilities:

- Build the procurement-request form.
- Build the live agent-decision timeline.
- Display offers, rejected alternatives, selected plan, and fallback.
- Display wallet/payment states and explorer links.
- Display reservation tokens, pickup QR codes, and delivery confirmation.
- Prepare screenshots, final README, and demo narration.
- Initially work entirely against fixtures that match `packages/contracts`.

Person 1 must not edit backend, payment, shared-contract, or root configuration files.

### Person 2 - Buyer AI and deterministic optimization

Exclusive ownership:

```text
services/buyer-agent/**
```

Responsibilities:

- Implement objective parsing with structured output.
- Implement the explicit procurement state machine.
- Implement filtering and feasible-combination generation.
- Rank plans using total cost, reliability, expiry risk, and deadline.
- Produce typed `PurchaseIntent` objects.
- Call provider and payment-facing APIs.
- Implement seller and courier fallback behavior.
- Produce concise, auditable agent explanations.
- Write tests inside `services/buyer-agent/tests/**`.

Person 2 must never read wallet seeds or construct raw signed transactions.

### Person 3 - Marketplace, seller simulators, and courier simulators

Exclusive ownership:

```text
services/marketplace/**
services/providers/**
```

Responsibilities:

- Implement offer and quote discovery.
- Own the SQLite schema and migrations.
- Implement three seller configurations and two courier configurations.
- Implement inventory expiry, price changes, reservation locking, and sold-out behavior.
- Add x402 middleware through the payment package's public adapter.
- Return reservations and delivery bookings after payment validation.
- Simulate one provider failure used by the demo.
- Write provider and marketplace tests within owned directories.

Person 3 must not edit the payment package or shared schemas directly.

### Person 4 - XRPL, x402, shared contracts, and integration

Exclusive ownership:

```text
packages/contracts/**
packages/payments/**
tests/e2e/**
docs/architecture/**
docker-compose.yml
Makefile
.env.example
```

Responsibilities:

- Publish shared schemas before parallel feature work begins.
- Create the XRPL/x402 buyer client wrapper.
- Create provider-side payment middleware adapters.
- Implement wallet-policy validation and safe secret loading.
- Implement invoice binding, idempotency, and transaction-receipt normalization.
- Complete a standalone Testnet x402 payment first.
- Build Docker Compose and root development commands.
- Own the architecture diagram.
- Build the full end-to-end test.
- Record validated transaction hashes for the submission.

Only Person 4 edits shared contracts and root orchestration files. Other contributors request changes rather than editing them.

## 12. Parallel Schedule

### Phase 0 - Contract freeze, 30-45 minutes

All four participants agree on:

- Demo input and expected output
- API endpoints and JSON shapes
- Wallet roles
- XRP Testnet as the payment environment
- Provider fixtures
- Required success and failure states

Person 4 writes the contracts. After this point, each person stays inside their owned paths.

### Phase 1 - Independent vertical work

All four work simultaneously:

| Person | Independent work |
| --- | --- |
| 1 | Build all screens against fixed JSON fixtures |
| 2 | Build agent and optimizer against fixture provider responses |
| 3 | Build provider APIs with a temporary payment-verification stub |
| 4 | Build and test x402/XRPL payment flow independently |

No contributor should wait for another implementation during this phase.

### Phase 2 - Integration

1. Person 4 proves one standalone x402 payment on XRPL Testnet.
2. Person 3 swaps the payment stub for Person 4's public adapter.
3. Person 2 swaps fixture providers for the live marketplace/provider endpoints.
4. Person 1 swaps JSON fixtures for buyer-agent API responses.
5. Person 4 runs and fixes the end-to-end orchestration without editing another person's internals.

### Phase 3 - Hardening and presentation

| Person | Final focus |
| --- | --- |
| 1 | UX polish, README, screenshots, and presentation flow |
| 2 | Decision quality, explanations, budget enforcement, and fallback |
| 3 | Atomic reservations, deterministic demo data, and provider failures |
| 4 | Payment reliability, E2E test, transaction links, and architecture |

## 13. Merge-Conflict Prevention Rules

1. Each person has exclusive ownership of the paths listed above.
2. Only Person 4 changes root development files and shared contracts.
3. Only Person 1 changes the final README.
4. Each service keeps its own dependency file inside its directory.
5. Services communicate via HTTP and frozen schemas.
6. Every contributor keeps tests inside their owned directory, except the E2E suite owned by Person 4.
7. Shared-contract changes are requested from Person 4.
8. Use these branches:

```text
feature/frontend
feature/buyer-agent
feature/providers
feature/xrpl-payments
```

9. Merge small contract-compatible changes frequently.
10. Do not perform large formatting passes across files owned by other contributors.

## 14. Demo Script

1. Enter: 100 vegetarian meals, delivery by 6 PM, budget 120 XRP.
2. Show the agent discovering three sellers and two couriers.
3. Show the agent rejecting at least one dietary-incompatible or expired offer.
4. Show two valid multi-seller plans with different total costs and risks.
5. Let the agent select a plan and explain why.
6. Simulate one selected seller becoming unavailable.
7. Show automatic replanning without exceeding the budget.
8. Trigger a seller reservation endpoint and visibly receive HTTP 402.
9. Show the buyer agent authorizing and completing an XRPL Testnet payment.
10. Show the returned reservation token and transaction hash.
11. Repeat for the remaining seller or courier if time permits.
12. Finish with a single outcome screen:

```text
100 vegetarian meals secured
Total food cost: [amount] XRP
Delivery cost: [amount] XRP
Total spent: [amount] XRP
Expected arrival: 5:35 PM
Food rescued: 100 meals
XRPL transactions: [explorer links]
```

## 15. Definition of Done

- A user can enter quantity, diet, deadline, destination, and budget.
- The agent returns a structured procurement goal.
- The system exposes at least three food offers and two courier quotes.
- The planner produces and compares multiple valid plans.
- The agent explains its economic decision.
- One provider failure causes successful replanning.
- A protected endpoint returns HTTP 402.
- The agent completes at least one real XRPL Testnet payment.
- The provider returns useful value only after validated payment.
- The UI displays the reservation, delivery result, and explorer link.
- Wallet seeds never appear in logs, commits, prompts, or UI.
- Private order details remain off-chain.
- Setup instructions work from a fresh clone.
- The architecture diagram and builder feedback are complete.

## 16. Explicit Non-Goals

Do not build these during the hackathon unless every definition-of-done item already works:

- Consumer mobile application
- Production food-safety certification
- Live integrations with restaurants or POS systems
- Real courier dispatch
- Multi-city routing
- XRPL escrow
- RLUSD support
- NFT-based food listings
- On-chain storage of inventory or personal data
- Complex auction or negotiation protocols
- Multiple LLM-based seller agents

## 17. Guidance for a New AI Chat

When helping with this project:

1. Preserve the fixed stack and file-ownership boundaries.
2. Do not replace the product with a generic food marketplace.
3. Keep the buyer agent as the main intelligent actor.
4. Keep optimization and payment authorization deterministic.
5. Use x402-protected standard XRPL payments, not escrow, for the MVP.
6. Default to XRPL Testnet and XRP.
7. Never read, print, or commit wallet seeds.
8. Ensure every paid endpoint returns identifiable value after settlement.
9. Optimize for one reliable end-to-end demo before adding features.
10. Explain how each change supports customer need, agent decision, payment, or value delivery.

## 18. Final Pitch

> SurplusFlow helps community kitchens acquire affordable meals from fragmented, expiring inventory. A buyer defines the quantity, dietary policy, deadline, destination, and budget; an AI agent discovers the best combination of surplus food, pays sellers and couriers through x402 on XRPL, and returns confirmed reservations and a delivery plan before the food becomes waste.

## 19. Authoritative References

When repository instructions and an external article differ, follow the repository instructions for hackathon eligibility and judging.

- Hackathon requirements: `README.md`
- Hackathon resource index: `resources.md`
- Feedback setup: `agent-instruction.md` and `hook/INSTALL.md`
- XRPL AI Starter Kit overview: <https://ripple.com/insights/xrpl-ai-starter-kit/>
- XRPL x402 quickstart: <https://xrpl-x402.t54.ai/docs/quickstart>
- XRPL x402 Python buyer: <https://xrpl-x402.t54.ai/docs/client-guides/python>
- XRPL x402 FastAPI merchant: <https://xrpl-x402.t54.ai/docs/merchant-guides/fastapi>
