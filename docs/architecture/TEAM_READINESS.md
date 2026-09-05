# Team Start Readiness

## Current status

The project is ready for the four contributors to begin independent implementation against Contract Freeze v1.0.0.

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

### Person 1: ready

Can build the entire UI using the frozen `AgentRun`, offer, quote, reservation, booking, and failure fixtures. No backend dependency is required to begin.

### Person 2: ready

Can build the buyer-agent state machine and Pydantic models from the schemas. Provider discovery and payment calls can begin as fixture-backed adapters.

### Person 3: ready

Can build marketplace, seller, and courier services from the OpenAPI paths. Payment verification can begin behind a stub that returns the frozen receipt shape.

### Person 4: independent foundation complete

The contracts, real `x402-xrpl` buyer/provider adapters, deterministic wallet
policy, durable invoice/payment journals, paid-response replay, receipt
normalization, transaction status lookup, standalone provider, dependency lock,
system architecture, and an offline end-to-end x402 loop are created. The
funded standalone x402 payment is validated on XRPL Testnet. The remaining
Person 4 work is root orchestration once service commands exist and the complete
cross-service E2E test.

Live proof: `77766F4E2E4B1AD39D7EA21F7188E3D8615886110D6676570F1F9949C8A0E173`
([Testnet explorer](https://testnet.xrpl.org/transactions/77766F4E2E4B1AD39D7EA21F7188E3D8615886110D6676570F1F9949C8A0E173)).

## Items intentionally not blocking parallel work

- Docker Compose is not yet useful because service implementations do not exist.
- Real Testnet wallet addresses are not stored in fixtures and must be supplied through ignored environment files.
- OpenAI and XRPL credentials are intentionally absent.
- Production food-safety, courier, and inventory integrations are outside the MVP.

## Integration gate

The project becomes demo-ready, rather than merely development-ready, only when:

1. Complete: Person 4 proved a real x402 XRPL Testnet payment using the implemented adapter.
2. Person 3 replaces the payment stub with Person 4's adapter.
3. Person 2 calls the live provider APIs and demonstrates replanning.
4. Person 1 connects the UI to `GET /api/runs/{runId}`.
5. The E2E path returns paid reservations, delivery confirmation, and explorer links.
