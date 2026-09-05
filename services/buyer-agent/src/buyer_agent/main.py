"""FastAPI application for the buyer agent (port 8001).

Responses are emitted as the frozen contract's exact wire form rather than a
FastAPI-derived schema, because `packages/contracts/openapi.yaml` is the source
of truth and this service must match it byte for byte.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import config, ids, timeutil
from .discovery import build_discovery_client
from .models import ApiError, ErrorCode, ProcurementRequest
from .parsing import ParseError, build_goal
from .payments import build_payment_client
from .policy import load_policy
from .state_machine import ProcurementAgent, new_state
from .store import IdempotencyConflict, RunStore

log = logging.getLogger(__name__)

IDEMPOTENCY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")

STATUS_FOR_ERROR: dict[ErrorCode, int] = {
    "invalid_request": 422,
    "not_found": 404,
    "provider_unavailable": 503,
    "budget_exceeded": 409,
    "policy_rejected": 409,
    "offer_sold_out": 409,
    "offer_expired": 409,
    "quote_expired": 409,
    "internal_error": 500,
}


def error_response(
    error: ErrorCode, message: str, *, retryable: bool = False, status: int | None = None
) -> JSONResponse:
    payload = ApiError(
        error=error, message=message, retryable=retryable, request_id=ids.unique("request")
    )
    return JSONResponse(
        status_code=status or STATUS_FOR_ERROR.get(error, 400), content=payload.wire()
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = config.settings()
    config.assert_no_seed_access()
    config.assert_payees_usable(settings)
    app.state.settings = settings
    app.state.store = RunStore()
    app.state.discovery = build_discovery_client(settings)
    app.state.payments = build_payment_client(settings)
    app.state.tasks = set()
    try:
        yield
    finally:
        for task in list(app.state.tasks):
            task.cancel()
        await app.state.discovery.aclose()
        await app.state.payments.aclose()


app = FastAPI(
    title="SurplusFlow Buyer Agent",
    version="1.0.0",
    description="Autonomous procurement agent for surplus food. Implements the "
    "Person 2 endpoints of Contract Freeze v1.0.0.",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def on_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """FastAPI's default body is not the public contract; map it to ApiError."""
    detail = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(part) for part in detail.get("loc", ())[1:]) or "body"
    return error_response(
        "invalid_request", f"{location}: {detail.get('msg', 'request is not valid')}"
    )


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse(status_code=200, content={"status": "ok"})


@app.post("/api/procure")
async def start_procurement(
    request: Request,
    body: ProcurementRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> JSONResponse:
    settings = request.app.state.settings
    store: RunStore = request.app.state.store

    if not IDEMPOTENCY_PATTERN.match(idempotency_key):
        return error_response(
            "invalid_request",
            "Idempotency-Key must match ^[A-Za-z0-9._:-]{8,128}$.",
        )

    fingerprint = hashlib.sha256(
        json.dumps(body.wire(), sort_keys=True).encode()
    ).hexdigest()
    try:
        existing = await store.claim(idempotency_key, fingerprint)
    except IdempotencyConflict:
        return error_response(
            "invalid_request",
            "This Idempotency-Key was already used for a different request body.",
            status=409,
        )
    if existing is not None:
        return JSONResponse(
            status_code=202,
            content=existing.wire(),
            headers={"Location": f"/api/runs/{existing.run_id}"},
        )

    now = timeutil.now()
    try:
        goal = build_goal(
            buyer_id=body.buyer_id,
            request_text=body.request_text,
            wallet_policy_id=body.wallet_policy_id,
            config=settings,
            reference=now,
        )
    except ParseError as exc:
        # Parsing runs inline so the 202 body carries a real goal, as the
        # AgentRun contract requires; an unparseable request never starts a run.
        return error_response("invalid_request", str(exc))

    policy = load_policy(body.wallet_policy_id, goal.max_total_spend_drops, settings)
    state = new_state(run_id=ids.unique("run"), goal=goal, policy=policy, now=now)
    await store.bind(idempotency_key, state.snapshot())

    agent = ProcurementAgent(
        discovery=request.app.state.discovery,
        payments=request.app.state.payments,
        settings=settings,
        on_update=lambda current: store.put_now(current.snapshot()),
    )

    if os.getenv("BUYER_AGENT_SYNCHRONOUS_RUNS") == "1":
        await agent.execute(state)
    else:
        task = asyncio.create_task(agent.execute(state))
        request.app.state.tasks.add(task)
        task.add_done_callback(request.app.state.tasks.discard)

    current = await store.get(state.run_id)
    assert current is not None
    return JSONResponse(
        status_code=202,
        content=current.wire(),
        headers={"Location": f"/api/runs/{current.run_id}"},
    )


@app.get("/api/runs/{run_id}")
async def get_run(request: Request, run_id: str) -> JSONResponse:
    store: RunStore = request.app.state.store
    run = await store.get(run_id)
    if run is None:
        return error_response("not_found", f"No procurement run with id {run_id}.")
    return JSONResponse(status_code=200, content=run.wire())
