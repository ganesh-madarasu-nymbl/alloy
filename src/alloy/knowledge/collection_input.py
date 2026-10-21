"""File input gates shared by the offline collection CLI and UI."""

import json

from pydantic import TypeAdapter

from alloy.contracts import Claim
from alloy.knowledge.collection import CollectionPlan, plan_collection
from alloy.knowledge.source_bundle import EvidenceBundle


def read_collection(data: bytes, *, reviewed: bool = False, max_audits: int = 3) -> CollectionPlan:
    if len(data) > 5_000_000:
        raise ValueError("Collection input must be smaller than 5 MB")
    if reviewed:
        evidence = EvidenceBundle.model_validate_json(data)
        # Keep blocked claims visible; the planner applies the eligibility gate.
        return plan_collection(evidence.claims, evidence=evidence, max_audits=max_audits)
    claims = TypeAdapter(list[Claim]).validate_python(json.loads(data))
    if any(c.source != "seed" for c in claims):
        raise ValueError("Synthetic collections must label every claim source='seed'; use a reviewed bundle otherwise")
    return plan_collection(claims, max_audits=max_audits)
