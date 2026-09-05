# SurplusFlow

**Community kitchens can't buy surplus food fast enough. So we gave the job to an agent.**

A procurement manager states one sentence — *"100 vegetarian meals, delivered by 6 PM,
no more than S$360 including delivery"* — and an AI buyer agent discovers surplus across
several providers, decides which combination to buy, pays each seller and courier over
x402 on the XRP Ledger, and hands back confirmed reservations before the food is thrown
away.

In the demo it secures all 100 meals for **S$222 — S$2.22 a meal** — and leaves S$138 of
the authorised budget unspent.

Ripple SingHacks 2026 · AI-Native Business on XRPL

---

## 🚨 SETUP A FEEDBACK HOOK!! 🚨

Copy and paste below instruction to your LLM client (Claude Code, Codex, etc):

```
Download feedback hook installation instructions from https://github.com/Singhacks-2026/ripple/blob/main/agent-instruction.md and install the hook accordingly.
```

This is crucial in securing feedback scores for the hackathon. Failure to set up the feedback hook properly may result in lower total score for the hackathon.

**Each teammate must run this on their own machine.** The hook registration is committed
in `.claude/settings.json`, but the identity config it needs lives at
`~/.xrpl-feedback-hook.json` and is per-developer. Without it every submission fails with
`missing config: teamName, hackerName`. See [hook/INSTALL.md](./hook/INSTALL.md) step 1.

## Load the XRPL agentic-resources skill (recommended)

This repo ships an agent skill that loads a curated set of XRPL AI and agent resources into your coding agent: agent wallets, x402 pay-per-call, agent credit, RLUSD, live amendment and fee status, and the XLS specs. It works in Claude Code, Cursor, and Codex.

From the repo root:

```
bash skills/install.sh
```

Then invoke it in your agent by typing `/xrpl-agentic-resources`, or just start XRPL agent work and the agent loads it by description. On first use, run `bash skills/xrpl-agentic-resources/scripts/refresh.sh` to pull the vendored repos and fresh docs indexes. See [skills/README.md](./skills/README.md) for per-agent details.

> On Windows, `skills/install.sh` creates symlinks that git may check out as plain text
> files. If the skill does not load, run `git config core.symlinks true` with Developer
> Mode enabled, then re-run the installer.

The full challenge statement is in
[Singhacks-challenge-statement.pdf](./Singhacks-challenge-statement.pdf); how we read it
is in [PROJECT_CONTEXT.md](./PROJECT_CONTEXT.md).

---

## The customer problem

Community kitchens, food banks and institutional canteens need affordable meals in bulk
under strict quantity, dietary, budget and delivery constraints. The surplus that would
serve them exists — in bakeries, hotels, supermarkets, caterers — but it is fragmented,
repriced constantly, and expires.

A procurement manager cannot watch a dozen providers at once, work out which combination
of two or three sellers reaches 100 meals at the lowest cost, compare courier routes, and
authorise several time-sensitive payments before another buyer takes the inventory. So
the food gets thrown away and the kitchen buys retail.

Every part of that job is mechanical except the constraints. That is what makes it an
agent's job rather than a better dashboard.

## Why this needs autonomous payment

The paid action is not a checkout at the end. It *is* the mechanism:

- Reserving surplus is what makes it exclusive. Until money moves, another buyer can take it.
- Prices and availability change inside the window a human takes to approve a payment.
- One order means several payments to several counterparties — two sellers and a courier.
- When a provider drops out mid-order, recovery has to happen in seconds, not at the next
  approval cycle.

The buyer authorises a budget and a set of rules. The agent decides the individual
economic actions inside it.

## What the demo shows

```
one sentence  →  discovery  →  rejection  →  plan comparison  →  provider failure
              →  replan  →  HTTP 402  →  XRPL settlement  →  confirmed reservations
```

| | |
|---|---|
| Rejects an invalid offer | Central Grill is the cheapest option and gets refused — not vegetarian. A hard rule in code, not model discretion. |
| Compares real alternatives | No single seller has 100 meals. Two multi-seller plans at S$222 vs S$223.50, with the reasoning shown. |
| Recovers from failure | A courier becomes unavailable after the plan is chosen. The agent replans without a human and stays inside budget. |
| Pays machine-to-machine | Provider middleware answers a paid request with HTTP 402 and x402 payment requirements; the validated standalone proof exercises that wire loop for real. |
| Settles on XRPL | One completed x402 commercial loop is validated on Testnet below. The full multi-provider rehearsal defaults to clearly labelled simulated receipts unless live spending is explicitly enabled. |
| Returns real value | Exclusive reservations with pickup tokens, and a booked courier — not just a hash. |

Full beat-by-beat narration: [docs/demo/DEMO_SCRIPT.md](./docs/demo/DEMO_SCRIPT.md).
Screenshots: [docs/demo/screenshots/](./docs/demo/screenshots/).

## Architecture

```
                    ┌──────────────────┐
   one sentence ───▶│   Web UI  :3000  │   Next.js 16 · React 19
                    └────────┬─────────┘
                             │ POST /api/procure · GET /api/runs/{runId}
                    ┌────────▼─────────┐
                    │ Buyer agent :8001│   LLM parses + explains
                    │                  │   deterministic code filters,
                    │                  │   combines, ranks, decides
                    └───┬──────────┬───┘
        discovery       │          │  PurchaseIntent (never a signed tx)
                        │          │
            ┌───────────▼──┐   ┌───▼──────────────┐
            │ Marketplace  │   │ Payments package │  policy checks, caps,
            │    :8002     │   │                  │  allowlist, invoice
            └───────┬──────┘   └───┬──────────────┘  binding, idempotency
                    │              │ signs locally
        ┌───────────▼──────────────▼────────────┐
        │  Sellers :8011-13 · Couriers :8021-22 │  return HTTP 402
        └───────────────────┬───────────────────┘
                            │ x402
                    ┌───────▼────────┐
                    │  XRPL Testnet  │  validated settlement
                    └────────────────┘
```

Detail: [docs/architecture/](./docs/architecture/).

**The model never signs anything.** The LLM parses the request, ranks trade-offs and
writes the explanations. It emits a typed `PurchaseIntent`. Deterministic code checks
quantity, expiry, diet, budget, per-transaction cap, payee allowlist and invoice
uniqueness before the wallet is asked for a signature.

## XRPL and x402

- **Network** XRPL Testnet (`xrpl:1`) · **Asset** XRP, denominated in drops
- **Display** every amount is shown in both SGD and XRP. Business figures lead in
  dollars — a kitchen manager does not think in XRP; settlement figures lead in XRP,
  because that is what the ledger moved. Conversion is display-only at an indicative
  S$3.00/XRP; every stored value stays an integer drops string. Production reads the rate
  from XRPL's own `PriceOracle` (XLS-47), enabled on mainnet today, rather than an
  external price API.
- **Protocol** x402 `exact` scheme over HTTP 402, hosted Testnet facilitator
- **Transaction type** standard `Payment`. No escrow — the paid product is a short-lived
  exclusive reservation, and escrow would add dispute complexity without improving the
  demonstration.

```
buyer agent calls a provider's reserve endpoint
  → provider returns 402 + PAYMENT-REQUIRED (x402 v2)
  → policy layer verifies network, asset, amount, payee, invoice, expiry, caps
  → buyer wallet signs an XRPL Payment locally
  → facilitator verifies and settles on Testnet
  → request retried with payment proof
  → provider returns the reservation
  → UI shows the validated hash
```

Only an opaque invoice reference and agent attribution go on-chain. Meal details, buyer
identity and delivery addresses stay off-chain.

### Validated transaction

On 2026-09-05, a provider-issued HTTP 402 challenge completed the real x402 loop for an
exclusive food reservation. The buyer signed locally, the facilitator settled it, XRPL
validated it with `tesSUCCESS`, and the provider returned the paid reservation.

- **Transaction:** [`77766F4E2E4B1AD39D7EA21F7188E3D8615886110D6676570F1F9949C8A0E173`](https://testnet.xrpl.org/transactions/77766F4E2E4B1AD39D7EA21F7188E3D8615886110D6676570F1F9949C8A0E173)
- **Ledger:** `20495875`
- **Amount:** `10000` drops (0.01 Test XRP)
- **Value delivered:** confirmed exclusive demo food reservation

This hash proves the real payment loop. It is separate from the default full-stack
rehearsal, whose synthetic receipts are visibly labelled **"Simulated — not settled on
XRPL"** and must not be presented as ledger evidence.

## Run it

**Frontend only** — no backend required, replays the frozen contract fixtures:

```bash
cd apps/web
pnpm install
pnpm dev            # http://localhost:3000
```

**Full stack** — starts the web app, buyer agent, marketplace, three sellers and two
couriers. The safe default uses live service discovery and simulated settlement, so it
needs neither an OpenAI key nor a funded wallet:

```bash
make run-stack       # http://localhost:3000
```

Run the repeatable browser integration gate (it starts and stops the stack itself):

```bash
make setup-all
make test-integration
```

Real multi-provider settlement is deliberately opt-in because it signs and submits
payments. Configure all receiving addresses and the buyer seed in the ignored `.env`,
obtain explicit authorization for that run, then use:

```bash
XRPL_WALLET_ENV_FILE=.env BUYER_AGENT_PAYMENT_MODE=x402 docker compose up
```

Do not use that live command as a routine health check. The default rehearsal and all
automated tests submit no XRPL transaction.

Requirements: Docker Compose for the full stack; Node 20+, pnpm 9+, Python 3.11+ and
`uv` for direct local development.

## Repository

```
apps/web/            Next.js UI                        (Person 1)
services/buyer-agent/  AI state machine and planner     (Person 2)
services/marketplace/  offers, reservations, SQLite     (Person 3)
services/providers/    seller and courier simulators    (Person 3)
packages/contracts/    OpenAPI + JSON schemas, frozen   (Person 4)
packages/payments/     XRPL wallet and x402 wrappers    (Person 4)
tests/e2e/             full demo path                   (Person 4)
docs/demo/             demo script and screenshots      (Person 1)
docs/architecture/     diagrams and handoffs            (Person 4)
```

Services talk only over the frozen contracts in `packages/contracts` — OpenAPI first,
then the JSON schemas, then the fixtures. No service imports another's source.

## Business model

A percentage of successfully reserved surplus, a delivery coordination fee, and
subscriptions for high-volume providers. Sellers currently pay staff time to list,
reprice and coordinate food that often gets binned anyway; buyers pay retail because
finding the surplus costs more than the saving. Both sides are better off with an agent
in the middle, and the model scales across providers, buyers and cities without changing
shape.

## Safeguards

- Wallet seeds load only from git-ignored env files, never reach the browser, the LLM,
  logs, or this repository
- Payments signed locally; the seed never crosses a network boundary
- Total-order and per-transaction spend caps, enforced in code
- Payee allowlist — a payment to any other address is refused before signing
- Unique invoice ids and idempotency keys prevent duplicate payment and double reservation
- Expired payment requirements are rejected
- Settlement must be validated before a provider returns the goods
- Private order data stays off-chain
