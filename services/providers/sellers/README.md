# SurplusFlow Seller Simulator

Person 3 service. One FastAPI codebase, configured per instance via
environment variables to represent one of the three demo sellers
(`packages/contracts/README.md` service table):

| `SELLER_ID` | Seller | Port |
| --- | --- | --- |
| `seller_bakery_001` | Green Oven Bakery | 8011 |
| `seller_hotel_001` | Harbour Hotel Kitchen | 8012 |
| `seller_grill_001` | Central Grill | 8013 |

## Endpoint

`POST /api/sellers/{sellerId}/offers/{offerId}/reserve` -- x402-protected.
First call (no `PAYMENT-SIGNATURE`) returns `402` with a `PAYMENT-REQUIRED`
challenge; the retry with `PAYMENT-SIGNATURE` and the same
`Idempotency-Key` settles payment via the shared
`surplusflow_provider_common.payments` adapter (a stub today -- see that
module's docstring for the swap-in point once Person 4 ships
`packages/payments`) and returns `201` with the confirmed `Reservation`.

Enforces, in order: seller-path match, `Idempotency-Key` ==
`PurchaseIntent.idempotencyKey`, resource-type/id/provider match, quantity
available, `payTo`/`amountDrops` consistency with the offer, intent
expiry, and invoice-ID uniqueness -- before ever contacting the payment
adapter. Successful settlement decrements `quantityAvailable` and marks
the offer `sold_out` once it reaches zero.

## Run

```bash
cd services/providers/sellers
uv sync --extra dev
SELLER_ID=seller_bakery_001 PORT=8011 uv run uvicorn app.main:app --reload --port 8011
```

Run three instances (different `SELLER_ID`/`PORT` pairs) for the full demo.
All instances share one SQLite file (`SURPLUSFLOW_DB_PATH`, default
`data/surplusflow.db` at the repo root) with the marketplace service.

## Test

```bash
cd services/providers/sellers
uv run pytest -q
```
