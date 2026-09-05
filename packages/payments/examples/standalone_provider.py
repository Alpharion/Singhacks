"""Run a local x402 seller endpoint before the seller service is available."""

import os
from pathlib import Path

from surplusflow_payments.config import load_project_environment
from surplusflow_payments.invoice_store import SQLiteInvoiceStore
from surplusflow_payments.provider import (
    ProviderPaymentConfig,
    create_standalone_provider_app,
)
from surplusflow_payments.provider_idempotency import SQLiteProviderResponseStore

load_project_environment()

pay_to_address = os.environ.get(
    "XRPL_PROVIDER_ADDRESS",
    "rPEPPER7kfTD9w2To4CQk6UCfuHM9c6GDY",
)

config = ProviderPaymentConfig(
    protected_paths="/paid/demo",
    price_drops="10000",
    pay_to_address=pay_to_address,
    facilitator_url="https://xrpl-facilitator-testnet.t54.ai",
)

app = create_standalone_provider_app(
    config,
    SQLiteInvoiceStore(Path(".data/provider-invoices.sqlite3")),
    response_store=SQLiteProviderResponseStore(
        Path(".data/provider-responses.sqlite3")
    ),
)
