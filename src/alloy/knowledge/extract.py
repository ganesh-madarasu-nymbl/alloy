"""Turn paper passages into Claim records."""

import json
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
        return float(text) if text is not None else None
    except ValueError:
        return None


def _coerce(value: str):
    number = _number(value)
    return number if number is not None else value


def extract_claims(paper: Paper, condition_keys: tuple[str, ...], start: int = 1) -> list[Claim]:
    prompt = (
        f"Paper: {paper.title} ({paper.id})\n"
        f"Condition keys to use where they apply: {', '.join(condition_keys)}\n\n"
        "Passages:\n" + "\n".join(f"- {p}" for p in paper.passages)
    )
    extracted = llm.parse(prompt, ExtractedClaims, system=SYSTEM).claims
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
