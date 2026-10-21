"""Turn paper passages into Claim records."""

import json
import math
import re
from pathlib import Path

from pydantic import BaseModel, Field

from alloy import llm
from alloy.contracts import Claim
from alloy.knowledge.bond import Paper


class Condition(BaseModel):
    key: str = Field(description="snake_case name, e.g. noise, dt, system, n_samples")
    value: str


class ExtractedClaim(BaseModel):
    method: str = Field(description="Method name in lowercase-kebab, e.g. sindy, weak-sindy")
    quantity: str = Field(description="What was measured, e.g. coef_error, equations_recovered")
    value: str | None = Field(None, description="Number as written, or null if qualitative")
    unit: str | None = None
    outcome: str | None = Field(None, description="Qualitative result in a few words")
    conditions: list[Condition] = Field(default_factory=list)
    quote: str = Field(description="The exact sentence the claim comes from")


class ExtractedClaims(BaseModel):
    claims: list[ExtractedClaim]


SYSTEM = """You extract quantitative scientific claims. Only record what a passage states.
Always record the conditions a result was measured under, using the condition keys given."""


def _number(text: str | None) -> float | None:
    try:
        value = float(text) if text is not None else None
        return value if value is not None and math.isfinite(value) else None
    except ValueError:
        return None


def _coerce(value: str):
    number = _number(value)
    return number if number is not None else value


def number_in_quote(value: float, quote: str) -> bool:
    """Check literal numeric support, without inferring unit conversions or scientific truth."""
    tokens = re.findall(
        r"(?<![\w.,])[+-]?(?:\d+(?:,\d{3})*(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?(?![\w,]|\.\d)", quote,
    )
    return any(_number(token.replace(",", "")) == value for token in tokens)


def extract_claims(paper: Paper, condition_keys: tuple[str, ...], start: int = 1) -> list[Claim]:
    if not paper.passages or not any(p.strip() for p in paper.passages):
        raise ValueError(f"{paper.id}: no source passages available for claim extraction")
    prompt = (
        f"Paper: {paper.title} ({paper.id})\n"
        f"Condition keys to use where they apply: {', '.join(condition_keys)}\n\n"
        "Passages:\n" + "\n".join(f"- {p}" for p in paper.passages)
    )
    extracted = llm.parse(prompt, ExtractedClaims, system=SYSTEM).claims
    for claim in extracted:
        quote = " ".join(claim.quote.split())
        if not quote or not any(quote in " ".join(p.split()) for p in paper.passages):
            raise ValueError(f"{paper.id}: extracted quote is absent from supplied passages")
        if claim.value is not None and _number(claim.value) is None:
            raise ValueError(f"{paper.id}: claim value is not a finite number")
        if claim.value is not None and not number_in_quote(_number(claim.value), claim.quote):
            raise ValueError(f"{paper.id}: numeric value is absent from the supporting quote")
    return [
        Claim(
            id=f"c{start + i}",
            paper=paper.id,
            title=paper.title,
            method=c.method,
            quantity=c.quantity,
            value=_number(c.value),
            unit=c.unit,
            outcome=c.outcome,
            conditions={cond.key: _coerce(cond.value) for cond in c.conditions},
            quote=c.quote,
        )
        for i, c in enumerate(extracted)
    ]


def load_seed(path: Path) -> list[Claim]:
    return [Claim(**c) for c in json.loads(Path(path).read_text(encoding="utf-8"))]
