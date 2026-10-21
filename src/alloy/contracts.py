"""The shared contracts. Knowledge code writes Claims and ExperimentSpecs; experiment code
reads them and writes RunResults. Change these only after both lanes agree."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Conditions = dict[str, Any]


class Claim(BaseModel):
    id: str
    paper: str  # DOI or arXiv id
    title: str | None = None
    method: str
    quantity: str
    value: float | None = None
    unit: str | None = None
    outcome: str | None = None  # qualitative result when the paper reports no number
    conditions: Conditions = Field(default_factory=dict)
    quote: str | None = None
    source: Literal["bond", "seed", "manual"] = "bond"


class Budget(BaseModel):
    runs: int = 60
    minutes: float = 5.0


class ExperimentSpec(BaseModel):
    task: str
    adapter: str
    method: str
    conditions: Conditions = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    seed: int = 0
    source_claims: list[str] = Field(default_factory=list)


class RunResult(BaseModel):
    id: str
    spec: ExperimentSpec
    metrics: dict[str, float] = Field(default_factory=dict)
    artifacts: dict[str, Any] = Field(default_factory=dict)
    seconds: float = 0.0
    ok: bool = True
    error: str | None = None


class Goal(BaseModel):
    question: str
    task: str = "equations-from-data"
    adapter: str = "pysindy"
    budget: Budget = Field(default_factory=Budget)


class Verdict(BaseModel):
    question: str
    status: Literal["resolved", "insufficient_evidence"]
    explanation: str
    deciding_conditions: list[str] = Field(default_factory=list)
    best_method: str | None = None
    evidence: list[str] = Field(default_factory=list)  # claim ids and run ids
