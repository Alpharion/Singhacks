# SurplusFlow Seller Agent

The other side of the market. Where the buyer agent is given a budget ceiling and
decides how to spend under it, the seller agent is given a **price floor** and decides
how to sell above it.

Runs on **port 8003**.

| Endpoint | Purpose |
| --- | --- |
| `POST /api/seller/listings` | Publish a listing and start the agent (202) |
| `GET /api/seller/listings/{listingId}` | Price, decisions, and timeline |
| `GET /api/seller/listings` | Every listing this process is running |
| `POST /api/seller/listings/{listingId}/demand` | Record buyer interest |
| `POST /api/seller/listings/{listingId}/sale` | Record units sold |
| `GET /health` | Liveness |

## Run it

```bash
cd services/seller-agent
uv venv && uv pip install -e ".[dev]"
.venv/bin/python -m uvicorn seller_agent.main:app --port 8003
```

```bash
curl -s -X POST http://localhost:8003/api/seller/listings \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: idem:seller:demo:v1' \
  -d '{"sellerId":"seller_bakery_001",
       "requestText":"Sell 60 vegetarian bakery meal boxes, collection by 11 PM, asking 2 XRP each but no less than 1.20 XRP."}'
```

## The problem it solves

A bakery at four in the afternoon has sixty vegetarian boxes and no time to price them.
Hold out for full price and the stock is thrown away at closing. Discount early and you
give away margin you never needed to. The decision has to be remade every few minutes,
against a deadline, and nobody is watching.

## What the seller delegates

One sentence, and one number they will not go under:

> Sell 60 vegetarian bakery meal boxes, collection by 11 PM, asking 2 XRP each but no
> less than 1.20 XRP.

The parser refuses to invent any of it. **A listing with no floor is rejected**, because
guessing one risks selling a seller's food under cost. A quantity and a collection
deadline are equally required. If no opening ask is stated the agent opens at 1.6× the
floor — an agent that opens *at* the floor has been delegated nothing.

## How it prices

The objective is to clear the stock before it expires, because unsold surplus is a total
loss rather than inventory carried to tomorrow. The price lives in the band between the
floor and the opening ask, and its position in that band is:

```
position = (1 - time_elapsed) + pace × 0.15 + demand × 0.35
price    = floor + band × clamp(position, 0, 1)
```

- **time_elapsed** walks the price down as the collection deadline approaches.
- **pace** is sell-through minus elapsed time. Selling faster than the clock holds the
  price up; falling behind pushes it down. Its weight is deliberately small — pace
  already contains elapsed time, and a large weight counts the clock twice and collapses
  to the floor around 60% of the way through the window.
- **demand** is recent buyer enquiries, saturating at six.

Prices are quoted to the nearest 0.01 XRP. Nobody sells bread at 1.971296 XRP.

## The floor is absolute

It is applied last, as a hard clamp, after rounding, and asserted afterwards. The tests
sweep the entire input space — every elapsed ratio, every stock level, every demand
level, including a floor that is not a round number — and assert the price never lands
under it. That guarantee is the only reason a seller would hand over pricing at all.

## Where the model is, and is not

The language model phrases one sentence of rationale for a decision the engine has
already made. It does not choose a price, cannot see the floor as negotiable, and its
output is never parsed back into a number. With no `OPENAI_API_KEY` the deterministic
phrasing runs alone and every test still passes. This mirrors the buyer agent exactly.

The service never sees a wallet seed and never signs anything; it sets prices, it does
not take money. Startup fails loudly if a seed is present in its environment.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `SELLER_AGENT_TICK_SECONDS` | `3` | Seconds between repricing ticks |
| `SELLER_AGENT_TIME_SCALE` | `200` | How much faster than wall-clock the window runs |
| `SURPLUSFLOW_TIMEZONE` | `Asia/Singapore` | How "by 9 PM" is read |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | — | Enables the rationale model; absent is fine |

**The compressed clock is disclosed in the UI.** A collection window is hours long and
unwatchable in real time, so the agent's clock runs faster and the listing carries
`timeScale` so the dashboard can say so. A compressed clock that is not stated is a lie
about how fast the agent works.

## Tests

```bash
.venv/bin/python -m pytest
```

32 tests, no network and no API key required.

## Not yet wired to the marketplace

The agent owns its listings in memory. It does not yet write `unit_price_drops` into
Person 3's marketplace, so a price it sets is not currently what the buyer agent pays.
The hook for that is `make_seller_price_resolver` in
`services/providers/sellers/app/payment_wiring.py`, which already resolves a reservation's
price per request — pointing it at this agent is what closes the loop.

Until then the dashboard's demand and sale buttons stand in for the signals the buyer
agent would otherwise raise, and the UI says so on the page.
