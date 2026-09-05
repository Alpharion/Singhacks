"""FastAPI application for the seller agent (port 8003).

The seller-side mirror of the buyer agent: one sentence in, an autonomous agent
working inside stated authority, and a readable record of every decision it
made. The authority here is a floor price rather than a budget ceiling, and the
agent's job is to clear perishable stock before it is thrown away without ever
selling under that floor.

| Endpoint | Purpose |
| --- | --- |
| `POST /api/seller/listings` | Publish a listing and start the agent (202) |
| `GET /api/seller/listings/{listingId}` | Read price, decisions, and timeline |
| `GET /api/seller/listings` | Every listing this process is running |
| `POST /api/seller/listings/{listingId}/demand` | Record buyer interest |
| `POST /api/seller/listings/{listingId}/sale` | Record units sold |
"""

from __future__ import annotations

import asyncio
import logging
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import config, ids
from .models import ApiError, DemandSignal, ListingRequest, SaleSignal
from .market import SimulatedMarket
from .parsing import ParseError, build_goal
from .state_machine import ListingAgent, new_listing

log = logging.getLogger(__name__)

IDEMPOTENCY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


def error_response(error: str, message: str, *, status: int, retryable: bool = False) -> JSONResponse:
    payload = ApiError(
        error=error, message=message, retryable=retryable, request_id=ids.unique("request")
    )
    return JSONResponse(status_code=status, content=payload.wire())


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = config.settings()
    config.assert_no_seed_access()
    app.state.settings = settings
    app.state.agents: dict[str, ListingAgent] = {}
    app.state.idempotency: dict[str, str] = {}
    app.state.tasks: set[asyncio.Task] = set()
    log.info(
        "seller agent ready: tick=%ss, time scale=%sx, simulated market=%s",
        settings.tick_seconds,
        settings.time_scale,
        settings.simulated_market,
    )
    try:
        yield
    finally:
        for task in list(app.state.tasks):
            task.cancel()


app = FastAPI(
    title="SurplusFlow Seller Agent",
    version="1.0.0",
    description="Autonomous dynamic pricing for perishable surplus, inside a seller's floor price.",
    lifespan=lifespan,
)

# The dashboard talks to this service through the web app's proxy, but allowing
# a direct browser call keeps the service usable on its own.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def on_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    detail = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(part) for part in detail.get("loc", ())[1:]) or "body"
    return error_response(
        "invalid_request",
        f"{location}: {detail.get('msg', 'request is not valid')}",
        status=422,
    )


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse(status_code=200, content={"status": "ok"})


def _agent(request: Request, listing_id: str) -> ListingAgent | None:
    return request.app.state.agents.get(listing_id)


@app.post("/api/seller/listings")
async def create_listing(
    request: Request,
    body: ListingRequest,
    idempotency_key: str = Header(default="", alias="Idempotency-Key"),
) -> JSONResponse:
    settings = request.app.state.settings

    if idempotency_key and not IDEMPOTENCY_PATTERN.match(idempotency_key):
        return error_response(
            "invalid_request",
            "Idempotency-Key must match ^[A-Za-z0-9._:-]{8,128}$.",
            status=422,
        )

    if idempotency_key:
        existing = request.app.state.idempotency.get(idempotency_key)
        if existing:
            agent = _agent(request, existing)
            if agent:
                return JSONResponse(status_code=202, content=agent.listing.wire())

    try:
        goal = build_goal(seller_id=body.seller_id, request_text=body.request_text)
    except ParseError as error:
        return error_response("invalid_request", str(error), status=422)

    listing = new_listing(goal, time_scale=settings.time_scale)
    listing.simulated_market = settings.simulated_market
    agent = ListingAgent(
        listing,
        tick_seconds=settings.tick_seconds,
        llm_enabled=settings.llm_enabled,
        market=SimulatedMarket(listing.listing_id, enabled=settings.simulated_market),
    )
    agent.publish()

    request.app.state.agents[listing.listing_id] = agent
    if idempotency_key:
        request.app.state.idempotency[idempotency_key] = listing.listing_id

    task = asyncio.create_task(agent.run())
    request.app.state.tasks.add(task)
    task.add_done_callback(request.app.state.tasks.discard)

    return JSONResponse(
        status_code=202,
        content=listing.wire(),
        headers={"Location": f"/api/seller/listings/{listing.listing_id}"},
    )


@app.get("/api/seller/listings")
async def list_listings(request: Request) -> JSONResponse:
    agents: dict[str, ListingAgent] = request.app.state.agents
    listings = sorted(
        (agent.listing for agent in agents.values()),
        key=lambda listing: listing.created_at,
        reverse=True,
    )
    return JSONResponse(
        status_code=200, content={"listings": [listing.wire() for listing in listings]}
    )


@app.get("/api/seller/listings/{listing_id}")
async def get_listing(request: Request, listing_id: str) -> JSONResponse:
    agent = _agent(request, listing_id)
    if agent is None:
        return error_response("not_found", f"No listing with id {listing_id}.", status=404)
    return JSONResponse(status_code=200, content=agent.listing.wire())


@app.post("/api/seller/listings/{listing_id}/demand")
async def record_demand(request: Request, listing_id: str, body: DemandSignal) -> JSONResponse:
    agent = _agent(request, listing_id)
    if agent is None:
        return error_response("not_found", f"No listing with id {listing_id}.", status=404)
    if agent.listing.status in ("cleared", "expired", "withdrawn"):
        return error_response(
            "listing_closed", "This listing is no longer taking interest.", status=409
        )

    await agent.record_demand(body.quantity, body.source)
    return JSONResponse(status_code=200, content=agent.listing.wire())


@app.post("/api/seller/listings/{listing_id}/sale")
async def record_sale(request: Request, listing_id: str, body: SaleSignal) -> JSONResponse:
    agent = _agent(request, listing_id)
    if agent is None:
        return error_response("not_found", f"No listing with id {listing_id}.", status=404)
    if agent.listing.quantity_remaining <= 0:
        return error_response("listing_closed", "Everything has already sold.", status=409)

    await agent.record_sale(body.quantity)
    return JSONResponse(status_code=200, content=agent.listing.wire())
