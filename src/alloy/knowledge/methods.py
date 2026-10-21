"""Discovery engine: find methods that may fix the weakness behind a disagreement."""

from typing import Literal

from pydantic import BaseModel, Field

from alloy import llm
from alloy.knowledge import bond

# Offline fallback so the demo runs without Bond or an API key.
KNOWN_FIXES = {
    "noise": [
        ("smoothed-sindy", "Smooth the signal before taking derivatives."),
        ("ensemble-sindy", "Test whether bagging sparse fits improves robustness to noise."),
        ("smoothed-ensemble-sindy", "Test the unproven combination of smoothing and ensembling."),
    ],
}


class MethodCandidate(BaseModel):
    method: str = Field(description="Must be one of the adapter's supported methods")
    rationale: str
    evidence_status: Literal["engineering_hypothesis", "source_passage"] = Field(
        "engineering_hypothesis",
        description="source_passage means quote occurrence was checked, not that the proposal is scientifically proven",
    )
    source_paper: str | None = Field(
        None, description="Exact id of a retrieved paper; not proof it introduced the method",
    )
    source_quote: str | None = Field(None, description="Verbatim supporting passage from that paper")


class MethodCandidates(BaseModel):
    candidates: list[MethodCandidate]


def propose(weakness: str, baseline: str, supported: tuple[str, ...], offline: bool = False) -> list[MethodCandidate]:
    if offline:
        known = KNOWN_FIXES.get(weakness)
        if known is None:  # no literature prior for this weakness: try every other method
            known = [(m, f"untested against {weakness}") for m in supported]
        return [
            MethodCandidate(method=m, rationale=why)
            for m, why in dict(known).items() if m in supported and m != baseline
        ]

    papers = bond.search(f"methods that make {baseline} robust to {weakness}")
    notes = "\n\n".join(f"{p.title} ({p.id}):\n" + "\n".join(p.passages) for p in papers)
    result = llm.parse(
        f"The baseline method {baseline!r} fails when {weakness} changes.\n"
        f"Supported methods: {', '.join(supported)}\n\n"
        f"Pick supported methods most likely to fix it, best first. For a source-backed proposal, "
        f"use the exact retrieved paper id, a nonempty verbatim source_quote from its passages, "
        f"and evidence_status source_passage. Quote occurrence does not establish scientific truth. "
        f"Label unproven combinations and source-free proposals engineering_hypothesis. "
        f"Do not invent citations or present an engineering hypothesis as a published result.\n\n{notes}",
        MethodCandidates,
    )
    accepted = []
    seen = set()
    for candidate in result.candidates:
        if candidate.method not in supported or candidate.method == baseline or candidate.method in seen:
            continue
        has_citation = candidate.source_paper is not None or candidate.source_quote is not None
        if has_citation or candidate.evidence_status == "source_passage":
            quote = (candidate.source_quote or "").strip()
            if not quote or not any(
                paper.id == candidate.source_paper and any(quote in passage for passage in paper.passages)
                for paper in papers
            ):
                continue
        seen.add(candidate.method)
        accepted.append(candidate)
    return accepted
