"""Read saved results without executing experiments or trusting uploaded filesystem paths."""

import json
from pathlib import Path

from alloy.agent.loop import Investigation


def read_investigation(data: bytes) -> Investigation:
    if len(data) > 5_000_000:
        raise ValueError("Investigation records must be smaller than 5 MB")
    inv = Investigation.model_validate_json(data)
    cases = inv.challenge.get("cases", [])
    if not isinstance(cases, list) or not all(isinstance(case, dict) for case in cases):
        raise ValueError("Unseen cases must be a list of recorded cases")
    return inv


def read_campaign(data: bytes):
    from alloy.agent.campaign import Campaign
    from alloy.knowledge.collection import plan_collection

    if len(data) > 5_000_000:
        raise ValueError("Campaign records must be smaller than 5 MB")
    def reject_constant(value):
        raise ValueError(f"nonfinite JSON constant: {value}")

    campaign = Campaign.model_validate(json.loads(data, parse_constant=reject_constant))
    expected = plan_collection(campaign.plan.claims, evidence=campaign.plan.evidence,
                               max_audits=campaign.plan.max_audits)
    if campaign.plan != expected:
        raise ValueError("saved plan disagrees with deterministic screening")
    return campaign


def local_notebook(path: str | None, run_root: Path) -> bytes | None:
    if not path:
        return None
    try:
        candidate = Path(path).resolve()
        if candidate.suffix != ".ipynb" or not candidate.is_relative_to(run_root.resolve()):
            return None
        return candidate.read_bytes()
    except (OSError, RuntimeError):
        return None
