"""The language-model boundary.

Two jobs only: turn a sentence into structured constraints, and phrase why a
plan was chosen. Both have deterministic fallbacks, so the agent runs with no
API key and never fails a procurement run because the model was unavailable.

The model never sees a wallet seed, never chooses a payee, and never decides an
amount. Its parsed output is re-validated by deterministic code before use.
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, Field

from .config import Settings

log = logging.getLogger(__name__)

PARSE_SYSTEM_PROMPT = """You convert a food-procurement request into structured constraints.
Extract only what the text states. Use null for anything the text does not state.
Never invent a budget, a quantity, or a deadline.
Times are wall-clock in the buyer's local timezone; return them as 24-hour HH:MM.
Budget is the maximum total spend in XRP, including delivery."""

EXPLAIN_SYSTEM_PROMPT = """You explain a procurement agent's choice to the buyer in one sentence.
State the concrete reason the chosen plan beat the alternatives, using the numbers given.
Do not add advice, praise, or detail that is not in the input."""


class ParsedConstraints(BaseModel):
    """Soft output from the model. Every field is re-checked downstream."""

    meal_count: int | None = Field(default=None, ge=1, le=10000)
    dietary_tags: list[
        Literal[
            "vegetarian", "vegan", "halal", "kosher", "gluten_free", "nut_free", "dairy_free"
        ]
    ] = Field(default_factory=list)
    destination_zone: str | None = None
    destination_address: str | None = None
    deadline_local_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    max_spend_xrp: float | None = Field(default=None, gt=0)
    min_seller_reliability: float | None = Field(default=None, ge=0, le=1)
    optimization_priority: (
        Literal["balanced", "lowest_cost", "highest_reliability", "lowest_waste"] | None
    ) = None


def parse_constraints(text: str, config: Settings) -> ParsedConstraints | None:
    """Ask the model for structured constraints. Returns ``None`` when unavailable."""
    if not config.llm_enabled:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=config.openai_api_key)
        response = client.responses.parse(
            model=config.openai_model,
            input=[
                {"role": "system", "content": PARSE_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            text_format=ParsedConstraints,
        )
        return response.output_parsed
    except Exception as exc:  # noqa: BLE001 - the run must survive any model failure
        log.warning("structured parse unavailable, using deterministic parser: %s", exc)
        return None


def explain_selection(prompt: str, config: Settings) -> str | None:
    """One sentence of prose to accompany the deterministic reasons."""
    if not config.llm_enabled:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=config.openai_api_key)
        response = client.responses.create(
            model=config.openai_model,
            input=[
                {"role": "system", "content": EXPLAIN_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        text = (response.output_text or "").strip()
        return text or None
    except Exception as exc:  # noqa: BLE001
        log.warning("explanation unavailable: %s", exc)
        return None
