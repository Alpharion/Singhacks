# SurplusFlow Marketplace

Person 3 service. Port `8002` (see `packages/contracts/README.md` service table).

Aggregates free food-offer and courier-quote discovery and exposes
reservation status. Per `PROJECT_CONTEXT.md` section 5, this service is
infrastructure: it does not choose purchases and never holds the buyer's
wallet credentials. It shares the SQLite database directly with the seller
and courier simulators in `services/providers/**` (all owned by Person 3);
every other service must reach this data over HTTP.

## Endpoints

| Method | Path | Contract |
| --- | --- | --- |
| GET | `/health` | Liveness check |
| GET | `/api/offers` | `listFoodOffers` -- filters: `dietaryTag`, `availableAt`, `minQuantity` |
| POST | `/api/delivery/quotes` | `listDeliveryQuotes` |
| GET | `/api/reservations/{reservationId}` | `getReservation` |

`GET /api/transactions/{transactionHash}` is owned by Person 4 and is not
implemented here.

## Run

```bash
cd services/marketplace
uv sync --extra dev
uv run uvicorn app.main:app --reload --port 8002
```

## Test

```bash
cd services/marketplace
uv run pytest -q
```

Tests point `SURPLUSFLOW_DB_PATH` at a temp file per test, so they never
touch the shared demo database.
