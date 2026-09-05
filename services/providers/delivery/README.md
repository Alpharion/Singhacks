# SurplusFlow Courier Simulator

Person 3 service. One FastAPI codebase, configured per instance via
environment variables (`packages/contracts/README.md` service table):

| `PROVIDER_ID` | Courier | Port |
| --- | --- | --- |
| `courier_fast_001` | FastRoute Courier | 8021 |
| `courier_economy_001` | Economy Van | 8022 |

## Endpoint

`POST /api/delivery/{providerId}/book` -- x402-protected, same challenge
/settle/retry sequence as `services/providers/sellers`'s reservation
endpoint.

## Demo failure simulation

When `simulate_failure` is on for this instance (Economy Van, by default,
via `DEMO_ECONOMY_COURIER_FAILURE=true` in `.env.example`), every booking
attempt returns `503 provider_unavailable` before payment starts --
PROJECT_CONTEXT.md section 5: "Courier services... Simulate one capacity
or route failure for fallback testing." This is the one predictable
provider failure the demo script relies on to show the buyer agent
replanning onto FastRoute Courier. Override per-instance with
`COURIER_SIMULATE_FAILURE=true|false`.

## Run

```bash
cd services/providers/delivery
uv sync --extra dev
PROVIDER_ID=courier_fast_001 PORT=8021 uv run uvicorn app.main:app --reload --port 8021
PROVIDER_ID=courier_economy_001 PORT=8022 uv run uvicorn app.main:app --reload --port 8022
```

Both instances share one SQLite file (`SURPLUSFLOW_DB_PATH`, default
`data/surplusflow.db` at the repo root) with the marketplace and seller
services.

## Test

```bash
cd services/providers/delivery
uv run pytest -q
```
