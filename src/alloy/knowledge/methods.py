"""Discovery engine: find methods that may fix the weakness behind a disagreement."""

from pydantic import BaseModel, Field

from alloy import llm
from alloy.config import settings
from alloy.knowledge import bond

# Offline fallback so the demo runs without Bond or an API key.
KNOWN_FIXES = {
    "noise": [
        ("smoothed-sindy", "Smooth the signal before taking derivatives."),
        ("ensemble-sindy", "Bag many sparse fits so noisy terms drop out (Fasel et al. 2022)."),
        ("smoothed-ensemble-sindy", "Combine smoothing and ensembling."),
    ],
}


class MethodCandidate(BaseModel):
    method: str = Field(description="Must be one of the adapter's supported methods")
    rationale: str
    source_paper: str | None = Field(None, description="DOI or arXiv id that introduced it")


class MethodCandidates(BaseModel):
    candidates: list[MethodCandidate]


def propose(weakness: str, baseline: str, supported: tuple[str, ...], offline: bool = False) -> list[MethodCandidate]:
    if offline or not settings.bond_configured:
        known = KNOWN_FIXES.get(weakness)
        if known is None:  # no literature prior for this weakness: try every other method
            known = [(m, f"untested against {weakness}") for m in supported]
        return [MethodCandidate(method=m, rationale=why) for m, why in known if m in supported and m != baseline]

    papers = bond.search(f"methods that make {baseline} robust to {weakness}")
    notes = "\n\n".join(f"{p.title} ({p.id}):\n" + "\n".join(p.passages) for p in papers)
    result = llm.parse(
        f"The baseline method {baseline!r} fails when {weakness} changes.\n"
        f"Supported methods: {', '.join(supported)}\n\n"
        f"Using only these papers, pick the supported methods (or combinations listed above) "
        f"most likely to fix it, best first, and cite the paper behind each.\n\n{notes}",
        MethodCandidates,
    )
    return [c for c in result.candidates if c.method in supported and c.method != baseline]
