# SurplusFlow Payments

Person 4's isolated XRPL/x402 package. It provides the financial safety boundary between the buyer agent and paid seller/courier endpoints.

## Responsibilities

- Decode x402 v2 `PAYMENT-REQUIRED` challenges.
- Match the challenge to an already-selected `PurchaseIntent`.
- Enforce network, asset, recipient, amount, invoice, provider allowlist, per-payment cap, and total-order cap.
- Load the Testnet buyer wallet only at the signing boundary.
- Use the official `x402-xrpl` client to sign and settle.
- Normalize `PAYMENT-RESPONSE` into the frozen `PaymentReceipt` contract.
- Persist invoice and transaction status without storing wallet seeds or signed blobs.
- Expose a reusable FastAPI provider-middleware adapter.
- Replay a completed paid response on an identical idempotent retry without
  settling the invoice twice.

The package does not choose providers, optimize meal plans, or let an LLM sign transactions.

## Setup

```text
cd packages/payments
uv sync --all-groups
uv run pytest
```

Runtime versions and transitive dependencies are frozen in `uv.lock`.

To run the isolated seller endpoint before the seller service exists:

```text
uv run uvicorn examples.standalone_provider:app --port 8011
curl -i -X POST http://localhost:8011/paid/demo
```

The second command intentionally returns HTTP `402` plus a
`PAYMENT-REQUIRED` challenge. It does not submit a transaction.

For an interactive signing ceremony, the standalone provider can extend its
transaction and invoice windows without changing production defaults:

```text
XRPL_PROVIDER_MAX_TIMEOUT_SECONDS=3600
XRPL_PROVIDER_INVOICE_TTL_SECONDS=3600
```

Once ignored environment variables contain a Testnet buyer wallet and provider
address, check their validated public account state without signing:

```text
uv run python examples/check_testnet_readiness.py \
  --provider-env XRPL_BAKERY_PAY_TO
```

The output contains public addresses and balances only. This is a readiness
check, not a payment command.

From the repository root, `make test-person4` validates both the shared
contracts and this package.

## Required environment for a real Testnet payment

```text
XRPL_NETWORK=xrpl:1
XRPL_TESTNET_RPC_URL=https://s.altnet.rippletest.net:51234/
XRPL_FACILITATOR_URL=https://xrpl-facilitator-testnet.t54.ai
XRPL_BUYER_SEED=<ignored secret>
```

Do not pass `XRPL_BUYER_SEED` through a command argument, API body, log, fixture, or model prompt. It belongs only in an ignored `.env` file or a future external signer.

## x402 wire boundary

The SDK owns the base64 payment payloads:

```text
Provider -> buyer: PAYMENT-REQUIRED
Buyer -> provider: PAYMENT-SIGNATURE
Provider -> buyer: PAYMENT-RESPONSE
```

Application code works with normalized Pydantic objects and never constructs a competing x402 wire format.

## Teammate integration points

- The orchestrator constructs a validated `PurchaseIntent` and passes it to
  `PaymentExecutor.execute(...)` only after its selection decision is final.
- Seller and courier services call `install_provider_payment(...)` with their
  protected reservation or booking path and both persistent stores.
- The API layer returns `PaymentExecutionResult.receipt` using the frozen
  `PaymentReceipt` contract.
- Uncertain transactions are reconciled with `TransactionStatusClient`; they
  must never be blindly resubmitted.

## Live-payment safety

Tests use fake sessions and never touch XRPL. A live payment is a separate explicit command and requires a funded Testnet wallet, a valid Testnet recipient, a transaction preview, and current-session authorization before signing.

## Validated Testnet proof

On 2026-09-05, the standalone provider completed the full x402 loop for an
exclusive demo food reservation. The buyer paid 10,000 drops (0.01 Test XRP),
the facilitator settled the signed payment, XRPL validated it with
`tesSUCCESS`, and the provider returned the confirmed reservation.

- Transaction: `77766F4E2E4B1AD39D7EA21F7188E3D8615886110D6676570F1F9949C8A0E173`
- Ledger: `20495875`
- Explorer: <https://testnet.xrpl.org/transactions/77766F4E2E4B1AD39D7EA21F7188E3D8615886110D6676570F1F9949C8A0E173>
