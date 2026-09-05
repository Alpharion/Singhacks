# SurplusFlow — web

The buyer-facing UI. Owned by Person 1 (`apps/web/**`).

Next.js 16 (App Router) · React 19 · TypeScript 5 strict · Tailwind 4 · TanStack Query ·
Recharts · Playwright + Vitest.

## Run it

```bash
pnpm install
pnpm dev            # http://localhost:3000
```

No backend needed. The app defaults to replaying the frozen contract fixtures.

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

## Two data sources, one interface

Everything reads a run through `useRun()` in `src/lib/queries.ts`, which returns the same
shape either way:

```
NEXT_PUBLIC_DATA_SOURCE=fixtures   replay the contract fixtures in the browser
NEXT_PUBLIC_DATA_SOURCE=live       poll GET /api/runs/{runId} on :8001
```

Integration is that one variable. See `.env.local.example`.

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
