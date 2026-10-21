"""Bounded, deterministic screening. A numerical gap is a heuristic, not a contradiction."""

import json
import re
from dataclasses import asdict
from itertools import combinations
from typing import Any, Literal
from urllib.parse import unquote, urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

from alloy.contracts import Claim
from alloy.knowledge.conditions import check
from alloy.knowledge.source_bundle import PYSINDY_KEYS, EvidenceBundle, execution_issue

DEFAULTS = dict(system="lorenz", noise=0.0, noise_type="gaussian", dt=0.002, t_end=10.0, threshold=0.1)


def canonical_work(identifier: str) -> str:
    value = unquote(identifier.strip())
    parsed = urlsplit(value)
    if parsed.scheme.lower() in {"http", "https"}:
        host = parsed.netloc.lower()
        if host in {"doi.org", "dx.doi.org"}:
            value = parsed.path.lstrip("/")
        elif host in {"arxiv.org", "www.arxiv.org"}:
            value = "https://arxiv.org" + parsed.path
    doi = re.fullmatch(r"(?:https?://(?:dx\.)?doi\.org/|doi:\s*)?(10\.\d{4,9}/\S+)", value, re.I)
    if doi:
        return "doi:" + doi[1].lower()
    arxiv = re.fullmatch(
        r"(?:https?://(?:www\.)?arxiv\.org/(?:abs|pdf)/|arxiv:\s*)?"
        r"(\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?(?:\.pdf)?", value, re.I,
    )
    if arxiv:
        return "arxiv:" + arxiv[1].lower()
    if not value:
        raise ValueError("paper IDs must not be empty")
    return "unresolved:" + value


def pair_id(a: str, b: str) -> str:
    return json.dumps(sorted((a, b)), separators=(",", ":"), ensure_ascii=True)


class StrictRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class PairPlan(StrictRecord):
    id: str
    claims: tuple[str, str]
    disposition: Literal["incompatible", "blocked_evidence", "no_detected_discrepancy", "eligible", "deferred"]
    reasons: list[str]
    condition_report: dict[str, Any] = Field(default_factory=dict)
    gap: float = Field(default=0.0, ge=0, le=2)
    rank: int | None = Field(default=None, ge=1)
    ranking_reasons: list[str] = Field(default_factory=list)


class CollectionPlan(StrictRecord):
    version: Literal[1] = 1
    claims: list[Claim]
    canonical_works: dict[str, str]
    evidence: EvidenceBundle | None = None
    identity_warnings: list[str] = Field(default_factory=list)
    max_audits: int = Field(default=3, ge=1, le=3)
    max_works: Literal[20] = 20
    max_claims: Literal[100] = 100
    pairs: list[PairPlan]
    selected: list[str]

    @model_validator(mode="after")
    def references(self):
        ids = [c.id for c in self.claims]
        if len(ids) > self.max_claims or len(ids) != len(set(ids)) or any(not c.strip() for c in ids):
            raise ValueError("at most 100 claims with unique nonempty IDs")
        expected = {c.id: canonical_work(c.paper) for c in self.claims}
        if self.canonical_works != expected or len(set(expected.values())) > self.max_works:
            raise ValueError("invalid canonical works or more than 20 works")
        pairs = {p.id: p for p in self.pairs}
        expected_pairs = {pair_id(a, b) for a, b in combinations(sorted(ids), 2)}
        if len(pairs) != len(self.pairs) or set(pairs) != expected_pairs:
            raise ValueError("every claim pair must be represented exactly once")
        for p in self.pairs:
            if p.id != pair_id(*p.claims) or list(p.claims) != sorted(p.claims) or not p.reasons:
                raise ValueError("invalid pair references or missing reasons")
        if len(self.selected) > self.max_audits or len(set(self.selected)) != len(self.selected):
            raise ValueError("invalid selected queue")
        if set(self.selected) != {p.id for p in self.pairs if p.disposition == "eligible"}:
            raise ValueError("selected queue must match eligible pairs")
        for index, id in enumerate(self.selected, 1):
            if pairs[id].rank != index:
                raise ValueError("queue rank is inconsistent")
        return self


def _execution_gap(claim: Claim, evidence: EvidenceBundle | None) -> str | None:
    if claim.source != "seed":
        if evidence is None or claim not in evidence.runnable_claims():
            return "claim requires a matching reviewed eligible source and protocol"
        return execution_issue(claim)
    if evidence is not None:
        return "seed claims cannot be reviewed literature"
    # Only synthetic examples can use adapter defaults; these remain explicitly assumptions.
    filled = claim.model_copy(update={"conditions": DEFAULTS | claim.conditions})
    return execution_issue(filled)


def plan_collection(
    claims: list[Claim], *, evidence: EvidenceBundle | None = None, max_audits: int = 3,
) -> CollectionPlan:
    if not 1 <= max_audits <= 3:
        raise ValueError("max_audits must be from 1 to 3")
    if len(claims) > 100 or len({c.id for c in claims}) != len(claims) or any(not c.id.strip() for c in claims):
        raise ValueError("at most 100 claims with unique nonempty IDs")
    # JSON would turn NaN/Infinity into null and change screening on a saved round trip.
    try:
        json.dumps([c.model_dump() for c in claims], allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("collection input must be JSON-compatible with only finite numbers") from exc
    claims = sorted(claims, key=lambda c: c.id)
    works = {c.id: canonical_work(c.paper) for c in claims}
    if len(set(works.values())) > 20:
        raise ValueError("collection exceeds the limit of 20 canonical works")
    gaps = {c.id: _execution_gap(c, evidence) for c in claims}
    pairs = []
    for a, b in combinations(claims, 2):
        report = check(a, b, PYSINDY_KEYS)
        p = PairPlan(id=pair_id(a.id, b.id), claims=(a.id, b.id), disposition="incompatible",
                     reasons=["screening in progress"], condition_report=json.loads(json.dumps(asdict(report))))
        if works[a.id] == works[b.id]:
            p.reasons = ["same canonical work; not independent cross-paper evidence"]
        elif not report.comparable:
            p.disposition = "blocked_evidence" if report.missing else "incompatible"
            p.reasons = report.notes
        elif (a.value is None) != (b.value is None):
            p.reasons = ["numeric and qualitative claims cannot be compared"]
        elif gaps[a.id] or gaps[b.id]:
            p.disposition = "blocked_evidence"
            p.reasons = [f"{c.id}: {gaps[c.id]}" for c in (a, b) if gaps[c.id]]
        else:
            if a.value is not None:
                scale = max(abs(a.value), abs(b.value), 1e-9)
                p.gap = abs(a.value / scale - b.value / scale)
            else:
                p.gap = float(a.outcome.strip().lower() != b.outcome.strip().lower())
            p.disposition = "eligible" if p.gap > 0.25 else "no_detected_discrepancy"
            p.reasons = ["point-value screening heuristic; no statistical contradiction established"]
            if a.source == "seed" or b.source == "seed":
                p.reasons.append("synthetic claims; unstated settings use adapter assumptions")
        pairs.append(p)
    queue = [p for p in pairs if p.disposition == "eligible"]
    selected, covered = [], set()
    while queue and len(selected) < max_audits:
        def priority(p):
            return (-bool(p.condition_report["differing"]),
                    -len({works[c] for c in p.claims} - covered), -p.gap, p.id)
        p = min(queue, key=priority)
        new = {works[c] for c in p.claims} - covered
        p.rank = len(selected) + 1
        p.ranking_reasons = [f"explicit condition differences: {bool(p.condition_report['differing'])}",
                             f"new canonical works: {len(new)}", f"normalized gap: {p.gap:g}",
                             "stable pair ID breaks remaining ties"]
        selected.append(p.id)
        covered.update(new)
        queue.remove(p)
    for p in queue:
        p.disposition = "deferred"
        p.reasons.append("selection limit reached")
    return CollectionPlan(
        claims=claims, canonical_works=works, evidence=evidence, pairs=pairs, selected=selected, max_audits=max_audits,
        identity_warnings=[f"{c.id}: unresolved work identity; no inferred alias merge" for c in claims
                           if works[c.id].startswith("unresolved:")],
    )
