# SurplusFlow — web

The buyer-facing UI. Owned by Person 1 (`apps/web/**`).

Next.js 16 (App Router) · React 19 · TypeScript 5 strict · Tailwind 4 · TanStack Query ·
Recharts · Playwright + Vitest.

## Run it

The app defaults to **live** mode and talks to Person 2's buyer agent, so start that first:

```bash
# terminal 1 - the buyer agent (Person 2), port 8001
cd services/buyer-agent
uv venv && uv pip install -e ".[dev]"
.venv/bin/python -m uvicorn buyer_agent.main:app --port 8001

# terminal 2 - this app
cd apps/web
pnpm install
pnpm dev            # http://localhost:3000
```

With no backend running, dispatching a request will fail. To work on the UI alone, fall
back to the frozen fixtures:

```bash
NEXT_PUBLIC_DATA_SOURCE=fixtures pnpm dev
```

## Scripts

| Command | What it does |
| --- | --- |
| `pnpm dev` | Dev server on :3000 |
| `pnpm build` | Production build |
| `pnpm typecheck` | `tsc --noEmit` |
| `pnpm test` | Vitest unit tests |
| `pnpm e2e` | Playwright pass over the demo script |
| `pnpm sync:contracts` | Re-read `packages/contracts` (types + fixtures) |
| `pnpm screenshots` | Capture `docs/demo/screenshots` (needs `pnpm dev` running) |
| `pnpm verify:live` | Walk the real journey against a running buyer agent |

## Two data sources, one interface

Everything reads a run through `useRun()` in `src/lib/queries.ts`, which returns the same
shape either way:

```
NEXT_PUBLIC_DATA_SOURCE=live       poll GET /api/runs/{runId}   (default, the demo path)
NEXT_PUBLIC_DATA_SOURCE=fixtures   replay the contract fixtures in the browser
```

Integration is that one variable. See `.env.local.example`.

Fixture mode adds a playback clock and a "Demo data" badge; live mode has neither, because
the run advances when the agent actually does something.

### The API is proxied, not called cross-origin

The browser calls `/api/...` on this origin, and the rewrite in `next.config.ts` forwards it
to the buyer agent (`BUYER_AGENT_ORIGIN`, default `http://localhost:8001`). That keeps every
request same-origin — which is what makes live mode work at all, since the buyer agent is a
plain FastAPI app with no CORS middleware and would reject a direct `fetch` from :3000 at the
preflight.

### Simulated payments are labelled as such

The buyer agent defaults to `BUYER_AGENT_PAYMENT_MODE=simulated`, which returns schema-valid
receipts whose transaction hash carries sixteen leading zeros. `src/lib/contracts/settlement.ts`
detects those, and the UI then refuses to say "Validated on XRPL", drops the explorer link, and
shows a run-level warning. A screenshot of a simulated run can never be mistaken for a settled
one — which is also why `pnpm verify:live` asserts it.

## Contracts

`packages/contracts` is owned by Person 4 and is never edited from here.
`pnpm sync:contracts` reads it and writes two things inside this app:

- `src/lib/contracts/generated.ts` — types generated from `openapi.yaml`
- `src/lib/demo/fixtures/` — verbatim copies of the fixtures

Import types from `src/lib/contracts/types.ts`, which puts friendly names over the
generated ones and provides accessors for the two places the contract spells the same
transaction hash differently (`PaymentReceipt.transaction` vs
`AgentDecision.transactionHash`).

Re-run `pnpm sync:contracts` after any contract release; TypeScript will point at
whatever drifted.

## Things worth knowing before you edit

**Money is never a number.** Every amount is an integer count of drops in a decimal
string. `src/lib/format/drops.ts` does all arithmetic in `BigInt` and formats by moving
the decimal point, so no value passes through a float. Use it; do not `parseFloat` a
drops string.

**Amounts are shown in both currencies.** `src/lib/format/money.ts` converts drops to SGD
cents in BigInt (display only - nothing is ever stored in dollars), and
`components/common/Money.tsx` renders the pair. Business figures lead in dollars
(`<Money drops={...} />`); settlement figures lead in XRP (`lead="xrp"`), because the
ledger moved XRP and a judge has to check it against the explorer. The rate is one
constant, labelled in the UI as an indicative demo assumption.

**Explorer URLs come from the backend.** `PaymentReceipt.explorerUrl` is rendered as
given. The frontend does not build explorer links — picking the network prefix belongs to
the payment layer.

**A rejected offer still has `status: "available"`.** Rejection is the agent's judgement,
recorded in `AgentDecision.rejectedAlternatives`, not a property of the offer. `OfferTable`
reads it from the decisions.

**The run fixture ships with empty `offers` and `deliveryQuotes`.** `agent-run.json`
references `offer_bakery_001` but carries no offers, so anything resolving an id to a
seller name uses `food-offers.json` / `delivery-quotes.json`. The demo projection merges
them at the discovery beat.

**The demo script is derived, not invented.** `src/lib/demo/script.ts` expands the
fixture's six events into the thirteen beats the demo narrative needs. Every price,
seller, hash and reason comes from the fixture; the only authored item is the
`select_plan` decision, which the fixture omits. `runProjection.test.ts` asserts the final
beat is byte-equal to the fixture's end state.

**Fixture mode says so.** The demo-data badge is deliberate — fixture hashes are synthetic
and unfunded, and a screenshot without the badge would imply a settlement that never
happened.

## Layout

```
src/
├── app/                     routes: / and /runs/[runId]
├── components/
│   ├── common/              Panel, Badge, Xrpl, status maps
│   ├── procurement/         request form, delegated authority
│   └── run/                 the dashboard and its panels
└── lib/
    ├── contracts/           generated types + friendly aliases
    ├── format/              drops (BigInt) and time
    ├── api/                 live client, config
    ├── demo/                fixtures, script, projection, playback clock
    └── queries.ts           useRun / useStartProcurement
```
