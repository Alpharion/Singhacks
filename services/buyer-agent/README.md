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
| `BUYER_AGENT_PAYMENT_ADAPTER` | `surplusflow_payments:build_client` | Person 4's factory |
| `MARKETPLACE_BASE_URL` | `http://localhost:8002` | Marketplace service |
| `SURPLUSFLOW_TIMEZONE` | `Asia/Singapore` | How "by 6 PM" is read |
| `BUYER_AGENT_ALLOWED_PAYEES` | fixture payees | Approved recipient allowlist |
| `BUYER_AGENT_MAX_TX_DROPS` | `70000000` | Per-transaction ceiling |
| `BUYER_AGENT_MAX_REPLANS` | `4` | Consecutive provider failures tolerated |
| `BUYER_AGENT_SIMULATED_FAILURES` | — | Provider ids that fail, for demos and tests |
| `BUYER_AGENT_SYNCHRONOUS_RUNS` | — | `1` runs inline before responding (tests) |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | — | Enables the model; absent is fine |

**Simulated payments settle nothing.** Their receipts carry a transaction hash
with sixteen leading zeros and a localhost explorer URL, and every timeline
entry says so, precisely so a simulated run can never be presented as evidence
of an XRPL payment. Real settlement needs `BUYER_AGENT_PAYMENT_MODE=x402`.

## Handoffs

**To Person 4 (payments).** Set `BUYER_AGENT_PAYMENT_ADAPTER=<module>:<factory>`.
The factory takes no arguments and returns an object with:

```python
async def purchase(intent: dict) -> dict
#   intent -> the wire form of a PurchaseIntent
#   returns {"statusCode": int, "body": dict, "receipt": dict | None}
```

`body` is the provider's `Reservation`, `DeliveryBooking`, or `ApiError`;
`receipt` is the normalized `PAYMENT-RESPONSE`. The 402 challenge, policy
re-validation, signing, settlement, and retry all live behind that call — this
service never sees them. On success the agent re-checks the receipt's invoice,
payee, amount, and network against the authorized intent and refuses a mismatch.

**To Person 3 (marketplace).** Set `BUYER_AGENT_DISCOVERY_MODE=http`. The agent
calls `GET /api/offers` and `POST /api/delivery/quotes`, then posts the
`PurchaseIntent` to the `reservationEndpoint` / `bookingEndpoint` carried on
each offer and quote, with `Idempotency-Key` equal to
`PurchaseIntent.idempotencyKey`.

**To Person 1 (frontend).** `GET /api/runs/{runId}` returns the full `AgentRun`:
`events` is the timeline, `decisions` the reasoning, `plans` the alternatives
compared, `spend` the budget position, and every receipt carries its
`explorerUrl`.

## Tests

```bash
.venv/bin/python -m pytest
```

84 tests, no network and no API key required. They assert against the frozen
contract rather than a local copy, so a contract change breaks them immediately:

- every fixture in `packages/contracts/fixtures` round-trips through the models
  byte for byte, and generated runs validate against Person 4's JSON Schemas;
- the optimizer independently reproduces `selected-plan.json` (60 meals from the
  bakery, 40 from the hotel, FastRoute, 74 XRP) and a full run reproduces the
  frozen `spend` block exactly;
- replanning is covered for a seller failing before payment, a seller failing
  after a partial order is already paid for, a courier failing at booking, and
  the case where a courier cannot reach a seller that has already been paid;
- no module reads a wallet seed or references transaction signing, and a leaked
  seed in the environment stops the service.

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
