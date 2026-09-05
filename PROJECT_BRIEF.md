# SurplusFlow - Concise Project Brief

Use this document as the starting context for a new AI chat working on this project. The detailed reference remains in `PROJECT_CONTEXT.md`.

## Hackathon Context

The challenge is to build an AI-native product that solves a real customer problem and demonstrates a complete commercial loop:

```text
customer need -> agent discovery -> agent decision -> payment -> value delivered
```

The payment must be economically meaningful, not a normal checkout triggered by a human. The user should define a goal, budget, and restrictions, while the AI decides which services are worth purchasing within that authority.

All blockchain activity must use the XRP Ledger. The prototype must complete at least one successful XRPL transaction and show its validated transaction hash or explorer link. The XRPL AI Starter Kit and agentic payment standards such as x402 or MPP are recommended rather than required. SurplusFlow deliberately uses the Starter Kit guidance and x402 because they fit its autonomous procurement flow; it does not use MPP.

Judges primarily care about:

- Whether the product solves a credible customer problem
- Whether AI is essential to the workflow
- Why autonomous payment makes the experience significantly better
- Technical quality, safety, traceability, and failure handling
- A clear and polished end-to-end demonstration

## Our Project: SurplusFlow

SurplusFlow helps community kitchens buy affordable meals from fragmented, time-sensitive surplus-food inventory.

A procurement manager provides a request such as:

> Secure 100 vegetarian meals, delivered by 6 PM, for no more than 120 XRP including delivery.

The AI buyer agent then:

1. Converts the request into quantity, dietary, location, deadline, reliability, and budget constraints.
2. Discovers offers from several food providers and quotes from couriers.
3. Rejects expired, unsafe, incompatible, unreliable, or unauthorized options.
4. Builds and compares combinations because one seller may not have enough meals.
5. Selects the best food-and-delivery plan within the delegated budget.
6. Explains why it selected that plan and rejected alternatives.
7. Pays selected sellers and couriers through x402 using XRP on XRPL Testnet.
8. Receives reservation tokens and delivery confirmation after payment.
9. Replans automatically if a provider becomes unavailable or a payment fails.

The useful value unlocked by payment is an exclusive food reservation or confirmed courier booking. Payment is therefore part of obtaining the service rather than a decorative transaction added after the decision.

## Target Users and Business Model

The primary MVP user is a community-kitchen procurement manager acquiring 50-200 meals under strict budget, dietary, delivery, and timing constraints.

Secondary users are bakeries, restaurants, hotels, supermarkets, caterers, and courier providers that want to sell expiring inventory or unused capacity without continuous manual coordination.

Possible revenue comes from a percentage of successful reservations, delivery-coordination fees, and subscriptions for high-volume providers.

## AI and Service Responsibilities

### Buyer agent

The buyer agent is the main intelligent actor. It parses natural language, evaluates trade-offs, chooses providers, creates structured purchase intents, explains decisions, and initiates replanning.

The language model does not sign transactions or enforce financial rules. Deterministic code checks quantities, expiry, diet, budget, provider allowlists, invoice uniqueness, and transaction limits before the payment component signs anything.

### Seller services

Three simulated seller services publish offers with meal type, quantity, price, location, expiry, and reliability. Their reservation endpoints return HTTP 402 payment requirements, lock inventory after validated payment, and return reservation tokens. Food-safety and expiry checks are deterministic.

### Courier services

Two simulated courier services publish capacity, price, route, and ETA. Their booking endpoints use the same x402 payment pattern and return delivery confirmation after settlement.

### Marketplace service

The marketplace stores and exposes offers, providers, reservations, and reputation information. It helps with discovery but does not make purchasing decisions or hold the buyer's wallet credentials.

## XRPL Payment Flow

```text
Buyer agent selects provider
    -> calls paid reservation or booking endpoint
    -> provider returns HTTP 402 payment requirements
    -> policy code validates price, recipient, invoice, network, and limits
    -> buyer wallet signs a standard XRPL Payment locally
    -> x402 facilitator verifies and settles it on XRPL Testnet
    -> request is retried with payment proof
    -> provider returns the reservation or booking
    -> UI shows the outcome and validated transaction hash
```

MVP decisions:

- XRPL Testnet network identifier: `xrpl:1`
- XRP is used for payments
- Standard XRPL `Payment` transactions are used
- No escrow, RLUSD, EVM chain, or XRPL EVM Sidechain
- Wallet seeds stay in ignored environment files and never reach the LLM, browser, logs, or repository
- At least one successful transaction must be visible during the demo

## Fixed Technology Stack

- Frontend: Next.js 16, React 19, TypeScript, Tailwind CSS, shadcn/ui, TanStack Query, Recharts
- APIs: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2, SQLite
- AI: OpenAI Responses API with structured Pydantic output plus a deterministic Python optimizer
- Payments: `xrpl-py`, `x402-xrpl`, XRP, XRPL Testnet, hosted Testnet facilitator
- Testing: pytest, FastAPI TestClient, Vitest, React Testing Library, Playwright
- Development: `uv`, `pnpm`, Docker Compose, `.env.example`

Do not introduce LangChain, LangGraph, Solidity, PostgreSQL, Redis, NFTs, escrow, or extra blockchain networks for the MVP.

## Four-Person Parallel Role Split

The team should agree on API schemas and demo fixtures first. After that, each person owns separate paths and avoids editing another person's files.

### Person 1 - Frontend, UX, and presentation

Owns:

```text
apps/web/**
docs/demo/**
README.md
```

Builds the procurement form, agent activity timeline, offer comparison, selected plan, fallback display, payment status, explorer links, reservation QR codes, screenshots, README, and demo narrative. Initially uses fixed JSON fixtures.

### Person 2 - Buyer AI and optimization

Owns:

```text
services/buyer-agent/**
```

Builds request parsing, the agent state machine, filtering, plan generation and ranking, structured purchase intents, explanations, provider calls, spending decisions, and seller/courier fallback logic. This service never receives wallet seeds or signs raw transactions.

### Person 3 - Marketplace and provider services

Owns:

```text
services/marketplace/**
services/providers/**
```

Builds offer discovery, the SQLite database, three seller simulators, two courier simulators, inventory expiry, reservation locking, x402-protected endpoints, delivery bookings, and one predictable provider failure for the demo.

### Person 4 - XRPL, x402, contracts, and integration

Owns:

```text
packages/contracts/**
packages/payments/**
tests/e2e/**
docs/architecture/**
docker-compose.yml
Makefile
.env.example
```

Freezes the shared schemas, builds buyer and provider x402 adapters, implements wallet-policy checks, safe secret loading, invoice binding, idempotency, transaction receipt handling, Docker Compose, the architecture diagram, and the end-to-end test. This person should prove one standalone XRPL Testnet x402 payment as early as possible.

## Integration Order

1. All four people agree on the demo request, JSON contracts, provider fixtures, and expected success/failure states.
2. Person 4 freezes shared schemas.
3. Everyone develops in parallel within their owned paths.
4. Person 4 proves the standalone XRPL payment.
5. Person 3 replaces payment stubs with Person 4's adapter.
6. Person 2 replaces provider fixtures with live provider APIs.
7. Person 1 replaces UI fixtures with the buyer-agent API.
8. Person 4 runs the complete end-to-end test.

## Minimum Successful Demo

The demo must show the user entering the meal request, the agent comparing multiple plans, rejection of at least one invalid offer, an explained economic decision, automatic recovery from one unavailable provider, an HTTP 402 response, a successful XRPL Testnet payment, and useful value returned as a reservation or delivery confirmation.

Final pitch:

> SurplusFlow helps community kitchens acquire affordable meals from fragmented, expiring inventory. A buyer defines the quantity, dietary policy, deadline, destination, and budget; an AI agent discovers the best combination, pays sellers and couriers through x402 on XRPL, and returns confirmed reservations and a delivery plan before the food becomes waste.
