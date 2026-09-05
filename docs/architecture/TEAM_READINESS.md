# Team Start Readiness

## Current status

Final integration is complete on top of Contract Freeze v1.0.0. All four contributor
branches are merged into the integration line, and the release gates below pass.

Completed foundations:

- Hackathon feedback hook configured for Codematch / Li Junyu
- Codex stop hook registered at project scope
- XRPL agentic-resources skill installed and refreshed
- Project context and concise brief present in the correct repository
- OpenAPI endpoint contract created
- JSON Schemas created
- Shared fixtures created
- x402 v2 header and XRPL Testnet conventions frozen
- File ownership and local service ports assigned
- Environment-variable names documented without secret values
- Contract validation command provided

## Start gates for everyone

Before coding, all four people must agree to:

- Treat `packages/contracts/openapi.yaml` as the endpoint source of truth.
- Use the JSON fixtures without renaming fields.
- Keep all XRP amounts as strings in drops.
- Keep wallet seeds outside the frontend, LLM context, API payloads, and logs.
- Request shared contract changes through Person 4.
- Demonstrate at least one real validated XRPL Testnet payment before submission.

## Person-specific start status

### Person 1: integrated

The UI supports both frozen fixtures and live polling of the buyer-agent API.

### Person 2: integrated

The state machine uses live marketplace discovery, the payment boundary, deterministic
policy checks and courier replanning.

### Person 3: integrated

The marketplace, three sellers and two couriers share inventory state and use Person 4's
request-scoped x402 pricing middleware.

### Person 4: integration complete

The contracts, real `x402-xrpl` buyer/provider adapters, deterministic wallet
policy, durable invoice/payment journals, paid-response replay, receipt
normalization, transaction status lookup, standalone provider, dependency lock,
system architecture, offline x402 loop, Docker Compose orchestration and cross-service
browser gate are created. The funded standalone x402 payment is validated on XRPL
Testnet. The full-stack simulated rehearsal has also passed without submitting another
transaction.

Live proof: `77766F4E2E4B1AD39D7EA21F7188E3D8615886110D6676570F1F9949C8A0E173`
([Testnet explorer](https://testnet.xrpl.org/transactions/77766F4E2E4B1AD39D7EA21F7188E3D8615886110D6676570F1F9949C8A0E173)).

## Items intentionally not blocking parallel work

- Docker Compose is not yet useful because service implementations do not exist.
- Real Testnet wallet addresses are not stored in fixtures and must be supplied through ignored environment files.
- OpenAI and XRPL credentials are intentionally absent.
- Production food-safety, courier, and inventory integrations are outside the MVP.

## Integration gate

1. Complete: real standalone x402 payment validated on XRPL Testnet.
2. Complete: provider stubs replaced by trusted request-price resolvers.
3. Complete: buyer agent calls the live marketplace and demonstrates replanning.
4. Complete: UI polls `GET /api/runs/{runId}`.
5. Complete: the full-stack browser gate returns reservations and delivery confirmation.
6. Optional and spend-bearing: repeat the full multi-provider path in x402 mode only
   after all five payees are configured, funded as needed and the run is authorized.
