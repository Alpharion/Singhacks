"""The models are the frozen contract, or they are wrong.

Every fixture must load into the matching model and serialize back to a byte
identical payload, and every AgentRun this service emits must validate against
Person 4's JSON Schemas.
"""

from __future__ import annotations

import json

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from buyer_agent.config import contracts_dir
from buyer_agent.models import (
    AgentRun,
    ApiError,
    DeliveryBooking,
    DeliveryQuoteRequest,
    DeliveryQuotesResponse,
    FoodOffersResponse,
    PaymentReceipt,
    PaymentRequirement,
    ProcurementPlan,
    ProcurementRequest,
    PurchaseIntent,
    Reservation,
)

from conftest import load_fixture

FIXTURE_MODELS = [
    ("procurement-request.json", ProcurementRequest),
    ("food-offers.json", FoodOffersResponse),
    ("delivery-quote-request.json", DeliveryQuoteRequest),
    ("delivery-quotes.json", DeliveryQuotesResponse),
    ("selected-plan.json", ProcurementPlan),
    ("purchase-intent.json", PurchaseIntent),
    ("payment-requirement.json", PaymentRequirement),
    ("payment-receipt.json", PaymentReceipt),
    ("reservation.json", Reservation),
    ("delivery-booking.json", DeliveryBooking),
    ("provider-failure.json", ApiError),
    ("agent-run.json", AgentRun),
]


@pytest.mark.parametrize(("filename", "model"), FIXTURE_MODELS, ids=lambda v: getattr(v, "__name__", v))
def test_fixture_round_trips_without_drift(filename, model):
    payload = load_fixture(filename)
    assert model.model_validate(payload).wire() == payload


def schema_validator(schema_name: str) -> Draft202012Validator:
    """Validator wired to every frozen schema so cross-file $refs resolve."""
    resources = []
    for path in sorted((contracts_dir() / "schemas").glob("*.schema.json")):
        with open(path, encoding="utf-8") as handle:
            schema = json.load(handle)
        resources.append((schema["$id"], Resource.from_contents(schema)))
    registry = Registry().with_resources(resources)
    target = dict(resources)[f"https://surplusflow.local/contracts/{schema_name}"]
    return Draft202012Validator(target.contents, registry=registry)


def test_agent_run_fixture_validates_against_frozen_schema():
    validator = schema_validator("agent-run.schema.json")
    assert list(validator.iter_errors(load_fixture("agent-run.json"))) == []


def test_extra_fields_are_refused():
    payload = load_fixture("payment-receipt.json") | {"note": "not in the contract"}
    with pytest.raises(Exception):
        PaymentReceipt.model_validate(payload)
