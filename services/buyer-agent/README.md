# SurplusFlow Buyer Agent

Person 2. The intelligent actor in SurplusFlow: it turns one sentence from a
procurement manager into a typed goal, discovers surplus food and courier
capacity, compares multi-seller combinations, authorizes spending inside a
delegated budget, and replans when a provider drops out.

Implements the Person 2 half of Contract Freeze v1.0.0 on **port 8001**:

| Endpoint | Purpose |
| --- | --- |
| `POST /api/procure` | Start an autonomous procurement run (202 + `Location`) |
| `GET /api/runs/{runId}` | Read the current state, decisions, and timeline |
| `GET /health` | Liveness |

## Run it

```bash
cd services/buyer-agent
uv venv && uv pip install -e ".[dev]"
.venv/bin/python -m uvicorn buyer_agent.main:app --port 8001
```

With no configuration it serves the frozen contract fixtures and simulates
settlement, so it runs end to end before the marketplace or the payments
package exist.

```bash
curl -s -X POST http://localhost:8001/api/procure \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: idem:demo:run:v1' \
  -d '{"buyerId":"buyer_kitchen_001","walletPolicyId":"policy_demo_001",
       "requestText":"Secure 100 vegetarian meals for our community kitchen, delivered to Queenstown by 6 PM, for no more than 120 XRP including delivery."}'
```

## What it does with that sentence

1. **Parse** into a typed `ProcurementGoal`: 100 meals, vegetarian, Queenstown,
   18:00 local, 120 XRP. Anything the text does not state is refused rather than
   guessed — a wrong budget is a wrong purchase.
2. **Discover** offers and courier quotes. Discovery is free; nothing is paid for
   here.
3. **Filter** on hard rules: dietary tags, expiry, pickup feasibility, seller
   reliability, courier capacity and ETA, and the approved-provider lists. Every
   rejection carries a reason the buyer can read.
4. **Plan.** No single seller covers 100 meals, so the optimizer enumerates
   subsets of eligible offers and allocates portions under four strategies
   (cheapest first, most reliable first, soonest-expiring first, even split),
   pairs each bundle with a courier that can actually collect from every seller
   in it, and scores the result.
5. **Select** the best plan for the buyer's stated priority, and record what it
   beat and why.
6. **Authorize and pay** each seller, then the courier, one policy check at a
   time.
7. **Replan** when a provider fails, using only the meals and budget that remain.

## Where the model is, and is not

The language model parses the request and phrases one sentence of the selection
rationale. That is all. It does not choose a provider, set an amount, approve a
payment, or see a wallet seed, and its parsed output is re-validated by
deterministic code before anything acts on it. With no `OPENAI_API_KEY` the
deterministic parser runs alone and every test still passes.

Filtering, combination generation, pricing, ranking, budget enforcement, payee
allowlisting, and stopping conditions are all deterministic: the same inputs
produce the same plan and the same spend, every time.

## Spending controls

`policy.py` is the only place a payment is approved, and it enforces:

- a per-transaction cap and a total-order cap, where the order cap can never
  exceed the budget the buyer actually stated;
- an approved-payee allowlist (`BUYER_AGENT_ALLOWED_PAYEES`) — a recipient
  discovered at runtime is not thereby trusted;
- a delivery reserve, so the agent cannot spend its courier budget on food and
  strand a paid order with no way to deliver it.

Each `PurchaseIntent` carries a snapshot of those limits so the payment boundary
can re-check the decoded x402 challenge against the same numbers.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `BUYER_AGENT_DISCOVERY_MODE` | `fixtures` | `fixtures` or `http` (marketplace) |
| `BUYER_AGENT_PAYMENT_MODE` | `simulated` | `simulated` or `x402` |
| `MARKETPLACE_BASE_URL` | `http://localhost:8002` | Marketplace service |
| `SURPLUSFLOW_TIMEZONE` | `Asia/Singapore` | How "by 6 PM" is read |
| `BUYER_AGENT_ALLOWED_PAYEES` | `XRPL_*_PAY_TO`, else fixtures | Approved recipient allowlist |
| `BUYER_AGENT_MAX_TX_DROPS` | `70000000` | Per-transaction ceiling |
| `BUYER_AGENT_MAX_REPLANS` | `4` | Consecutive provider failures tolerated |
| `BUYER_AGENT_SIMULATED_FAILURES` | — | Provider ids that fail, for demos and tests |
| `BUYER_AGENT_SYNCHRONOUS_RUNS` | — | `1` runs inline before responding (tests) |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | — | Enables the model; absent is fine |

**Simulated payments settle nothing.** Their receipts carry a transaction hash
with sixteen leading zeros and a localhost explorer URL, and every timeline
entry says so, precisely so a simulated run can never be presented as evidence
of an XRPL payment. Real settlement needs `BUYER_AGENT_PAYMENT_MODE=x402`.

**The approved payee list must hold real addresses in x402 mode.** The contract
fixtures ship synthetic placeholders (`rFoodA111...`) that match the contract's
address pattern but fail base58check, so the payment boundary rejects them.
Startup refuses `x402` mode with a placeholder allowlist and names the offending
addresses, rather than failing mid-run. Supply real ones through the
`XRPL_*_PAY_TO` variables in your ignored `.env`.

## Payment recovery

Person 4's payment errors split into two groups, and treating them alike is how
an agent pays twice:

| Failure | Recovery | Why |
| --- | --- | --- |
| `PolicyViolation` | replan | Refused before the journal opened; nothing signed |
| `PaymentExecutionError` | replan | No signed hash, so the requirement can be met elsewhere |
| `PaymentInProgressError` | **halt** | A payment is in flight; retrying could pay twice |
| `DuplicatePaymentError` | **halt** | Already settled, or identity fields reused |
| `PaymentReceiptError` | **halt** | Outcome uncertain after signing |
| `WalletConfigurationError` | **halt** | The wallet is unusable; further attempts are pointless |
| Receipt mismatch | **halt** | Money moved, but not as authorized |

On halt the run stops with the specific error, records a `stop` decision saying
why it is not replanning, and leaves the stored transaction hash for
reconciliation. It never tries another provider for the same resource.

## Handoffs

**Person 4 (payments) — integrated.** `BUYER_AGENT_PAYMENT_MODE=x402` drives
`surplusflow_payments.PaymentExecutor`. It is synchronous and `requests`-based,
so it runs on a worker thread rather than blocking the event loop. The agent
passes the frozen `PurchaseIntent` plus the run's `already_spent_drops`; the 402
challenge, policy re-validation, local signing, settlement, and the paid retry
all happen behind that call. On success the agent re-checks the receipt's
invoice, payee, amount, and network against the authorized intent.

**Person 3 (marketplace) — integrated.** `BUYER_AGENT_DISCOVERY_MODE=http` calls
`GET /api/offers` and `POST /api/delivery/quotes` on port 8002, then posts the
`PurchaseIntent` to the `reservationEndpoint` / `bookingEndpoint` carried on each
offer and quote, with `Idempotency-Key` equal to `PurchaseIntent.idempotencyKey`.

The agent deliberately does **not** pass the marketplace's `dietaryTag` filter.
Its own hard filters are the authoritative dietary check, and rejecting an
incompatible offer with a stated reason is part of the decision record — letting
the server pre-filter would hide those rejections from the buyer.

**To Person 1 (frontend).** `GET /api/runs/{runId}` returns the full `AgentRun`:
`events` is the timeline, `decisions` the reasoning, `plans` the alternatives
compared, `spend` the budget position, and every receipt carries its
`explorerUrl`.

## Tests

```bash
.venv/bin/python -m pytest
```

103 tests, no network and no API key required. They assert against the frozen
contract rather than a local copy, so a contract change breaks them immediately:

- every fixture in `packages/contracts/fixtures` round-trips through the models
  byte for byte, and generated runs validate against Person 4's JSON Schemas;
- the optimizer independently reproduces `selected-plan.json` (60 meals from the
  bakery, 40 from the hotel, FastRoute, 74 XRP) and a full run reproduces the
  frozen `spend` block exactly;
- replanning is covered for a seller failing before payment, a seller failing
  after a partial order is already paid for, a courier failing at booking, and
  the case where a courier cannot reach a seller that has already been paid;
- every `PaymentExecutor` error maps to the right recovery, an in-flight payment
  stops the run instead of replanning around it, and a receipt that disagrees
  with the authorized intent halts rather than being accepted;
- no module reads a wallet seed or references transaction signing, a leaked seed
  in the environment stops the service, and a synthetic fixture address is
  refused before any payment is attempted.

## Layout

```text
src/buyer_agent/
  main.py           FastAPI app, idempotency, ApiError mapping
  state_machine.py  the run loop: discover, plan, authorize, pay, replan
  planner.py        combination generation, risk scoring, ranking
  filtering.py      hard dietary, expiry, reliability, capacity rules
  policy.py         spending authorization
  intents.py        PurchaseIntent construction
  payments.py       the payment boundary (no signing, no seeds)
  discovery.py      fixture and HTTP marketplace clients
  parsing.py        sentence to ProcurementGoal
  llm.py            the model boundary, with deterministic fallbacks
  models.py         Contract Freeze v1.0.0 types
```
