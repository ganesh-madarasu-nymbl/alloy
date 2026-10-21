"""Portable reviewed evidence, kept separate from runnable scientific claims."""

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from alloy.contracts import Claim
from alloy.knowledge.conditions import check, measurement_issue
from alloy.knowledge.extract import number_in_quote
from alloy.knowledge.graph import EvidenceGraph

DEFAULT_BUNDLE = Path(__file__).resolve().parents[3] / "data/evidence/sindy_review.json"
PYSINDY_METHODS = ("sindy", "smoothed-sindy", "ensemble-sindy", "smoothed-ensemble-sindy")
PYSINDY_KEYS = ("system", "noise", "noise_type", "dt", "t_end", "threshold")


def execution_issue(claim: Claim) -> str | None:
    """Conservative profile for an exact literature reproduction with the current adapter."""
    if issue := measurement_issue(claim):
        return issue
    if claim.method not in PYSINDY_METHODS or claim.conditions.get("system") != "lorenz":
        return "method or system is unsupported by the current adapter"
    if set(claim.conditions) != set(PYSINDY_KEYS):
        return "exact reproduction needs every supported setting and no unsupported settings"
    if not check(claim, claim, PYSINDY_KEYS).comparable:
        return "conditions or measurement contain missing or nonfinite values"
    if claim.conditions["noise_type"] not in {"gaussian", "outliers"}:
        return "noise model is unsupported"
    for key in ("noise", "dt", "t_end", "threshold"):
        value = claim.conditions[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            return f"{key} must be a nonnegative number"
        if key in {"dt", "t_end"} and value == 0:
            return f"{key} must be positive"
    return None


class SourceEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_url: HttpUrl
    locator: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    evidence_type: Literal["abstract", "full_text"] = "abstract"
    review_status: Literal["unreviewed", "primary_text_reviewed"] = "unreviewed"
    reviewed_on: str | None = None
    stated_conditions: dict[str, Any] = Field(default_factory=dict)
    outcome_summary: str
    method_family: str
    exact_implementation_match: bool = False
    reproduction_eligible: bool = False
    blockers: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_eligibility(self):
        if self.reproduction_eligible and (
            self.evidence_type != "full_text" or self.review_status != "primary_text_reviewed"
            or not self.exact_implementation_match or self.blockers
        ):
            raise ValueError(
                "reproduction eligibility needs reviewed full text, matching implementation and no blockers"
            )
        return self


class EvidenceBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    description: str
    sources: list[SourceEvidence]
    claims: list[Claim] = Field(default_factory=list)
    claim_sources: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_sources(self):
        sources = {s.paper_id: s for s in self.sources}
        if len(sources) != len(self.sources):
            raise ValueError("source paper IDs must be unique")
        if len({c.id for c in self.claims}) != len(self.claims):
            raise ValueError("claim IDs must be unique")
        if set(self.claim_sources) != {c.id for c in self.claims}:
            raise ValueError("each claim needs exactly one source mapping")
        for claim in self.claims:
            source = sources.get(self.claim_sources[claim.id])
            if source is None or claim.paper != source.paper_id:
                raise ValueError("claim source does not identify the claimed paper")
            if source.review_status != "primary_text_reviewed" or source.evidence_type != "full_text":
                raise ValueError("bundle claims require reviewed full text")
            quote = " ".join((claim.quote or "").split())
            if not quote or quote not in " ".join(source.quote.split()):
                raise ValueError("claim quote is absent from reviewed evidence")
            if claim.source == "seed":
                raise ValueError("synthetic claims cannot be published evidence")
            if claim.method != source.method_family:
                raise ValueError("claim method differs from reviewed source")
            if claim.conditions != source.stated_conditions:
                raise ValueError("claim conditions must agree with reviewed source settings")
            if claim.value is not None and (not claim.unit or not number_in_quote(claim.value, quote)):
                raise ValueError("numeric claim needs explicit units and literal support")
        return self

    def runnable_claims(self) -> list[Claim]:
        sources = {s.paper_id: s for s in self.sources}
        return [c for c in self.claims if (
            sources[self.claim_sources[c.id]].reproduction_eligible
            and execution_issue(c) is None
        )]

    def summary(self) -> dict:
        runnable = self.runnable_claims()
        graph = EvidenceGraph()
        graph.add_claims(runnable)
        eligible_pair = any(a.paper != b.paper and check(a, b, PYSINDY_KEYS).comparable for a, b in graph.conflicts())
        return {
            "sources": len(self.sources), "reviewed_claims": len(self.claims),
            "runnable_claims": len(runnable),
            "eligible_cross_paper_pair": eligible_pair,
            "blockers": {s.paper_id: s.blockers for s in self.sources if s.blockers},
            "execution_gaps": {c.id: issue for c in self.claims if (issue := execution_issue(c))},
        }


def load_bundle(path: Path = DEFAULT_BUNDLE) -> EvidenceBundle:
    return EvidenceBundle.model_validate_json(Path(path).read_text(encoding="utf-8"))
