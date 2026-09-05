from __future__ import annotations

import asyncio

import pytest
from x402_xrpl.types import PaymentRequirements

from surplusflow_payments.invoice_store import SQLiteInvoiceStore

from conftest import PAYEE, SOURCE_TAG


def make_requirement() -> PaymentRequirements:
    return PaymentRequirements(
        scheme="exact",
        network="xrpl:1",
        amount="1000",
        asset="XRP",
        pay_to=PAYEE,
        max_timeout_seconds=600,
        extra={"invoiceId": "inv:store_001", "sourceTag": SOURCE_TAG},
    )


def test_persists_and_consumes_invoice(tmp_path) -> None:
    store = SQLiteInvoiceStore(tmp_path / "invoices.sqlite3")

    asyncio.run(store.put("inv:store_001", [make_requirement()], ttl_seconds=60))
    loaded = asyncio.run(store.get("inv:store_001"))
    assert loaded is not None
    assert loaded[0].to_dict() == make_requirement().to_dict()

    asyncio.run(store.consume("inv:store_001"))
    assert asyncio.run(store.get("inv:store_001")) is None


def test_expired_invoice_is_unavailable_and_can_be_deleted(tmp_path) -> None:
    store = SQLiteInvoiceStore(tmp_path / "invoices.sqlite3")
    asyncio.run(store.put("inv:store_001", [make_requirement()], ttl_seconds=-1))

    assert asyncio.run(store.get("inv:store_001")) is None
    assert store.delete_expired() == 1
    assert asyncio.run(store.get("inv:missing_001")) is None


def test_identical_unconsumed_invoice_can_be_reissued(tmp_path) -> None:
    store = SQLiteInvoiceStore(tmp_path / "invoices.sqlite3")
    requirement = make_requirement()
    asyncio.run(store.put("inv:store_001", [requirement], ttl_seconds=60))

    asyncio.run(store.put("inv:store_001", [requirement], ttl_seconds=60))

    loaded = asyncio.run(store.get("inv:store_001"))
    assert loaded is not None
    assert loaded[0].to_dict() == requirement.to_dict()


def test_invoice_id_cannot_change_payment_terms(tmp_path) -> None:
    store = SQLiteInvoiceStore(tmp_path / "invoices.sqlite3")
    asyncio.run(store.put("inv:store_001", [make_requirement()], ttl_seconds=60))
    changed = PaymentRequirements(
        scheme="exact",
        network="xrpl:1",
        amount="1001",
        asset="XRP",
        pay_to=PAYEE,
        max_timeout_seconds=600,
        extra={"invoiceId": "inv:store_001", "sourceTag": SOURCE_TAG},
    )

    with pytest.raises(ValueError, match="different payment requirements"):
        asyncio.run(store.put("inv:store_001", [changed], ttl_seconds=60))


def test_consumed_invoice_cannot_be_reissued(tmp_path) -> None:
    store = SQLiteInvoiceStore(tmp_path / "invoices.sqlite3")
    requirement = make_requirement()
    asyncio.run(store.put("inv:store_001", [requirement], ttl_seconds=60))
    asyncio.run(store.consume("inv:store_001"))

    with pytest.raises(ValueError, match="already been consumed"):
        asyncio.run(store.put("inv:store_001", [requirement], ttl_seconds=60))


def test_expired_invoice_can_be_reissued_with_same_terms(tmp_path) -> None:
    store = SQLiteInvoiceStore(tmp_path / "invoices.sqlite3")
    requirement = make_requirement()
    asyncio.run(store.put("inv:store_001", [requirement], ttl_seconds=-1))

    asyncio.run(store.put("inv:store_001", [requirement], ttl_seconds=60))

    assert asyncio.run(store.get("inv:store_001")) is not None
