from copy import deepcopy

import pytest
from pydantic import ValidationError

from alloy.knowledge.source_bundle import EvidenceBundle, load_bundle


def evidence():
    sources, claims = [], []
    for i, value in enumerate((0.1, 0.8)):
        paper = f"arxiv:2401.0000{i}"
        quote = f"The relative coefficient error is {value}."
        sources.append(dict(
            paper_id=paper, title=f"Paper {i}", source_url=f"https://arxiv.org/abs/2401.0000{i}",
            locator="Table 1", quote=quote, evidence_type="full_text",
            review_status="primary_text_reviewed", reviewed_on="2026-10-21",
            outcome_summary="Test fixture only", method_family="sindy",
            exact_implementation_match=True, reproduction_eligible=True,
            stated_conditions={"system": "lorenz", "noise": value},
        ))
        claims.append(dict(
            id=f"c{i}", paper=paper, method="sindy", quantity="coef_error", value=value,
            unit="dimensionless", conditions={"system": "lorenz", "noise": value}, quote=quote, source="manual",
        ))
    return dict(description="Synthetic validation fixture; not published evidence", sources=sources, claims=claims,
                claim_sources={c["id"]: c["paper"] for c in claims})


def test_reviewed_real_sources_do_not_imply_a_runnable_disagreement():
    bundle = load_bundle()
    assert len(bundle.sources) >= 2
    assert all(s.review_status == "primary_text_reviewed" for s in bundle.sources)
    assert not bundle.summary()["eligible_cross_paper_pair"]
    assert not bundle.runnable_claims()
    assert bundle.summary()["blockers"]


def test_eligible_pair_requires_reviewed_literal_claim_support():
    bundle = EvidenceBundle.model_validate(evidence())
    assert bundle.summary()["eligible_cross_paper_pair"]
    assert len(bundle.runnable_claims()) == 2


@pytest.mark.parametrize("change", [
    lambda b: b["claims"][0].update(quote="Invented result is 0.1."),
    lambda b: b["claims"][0].update(value=99),
    lambda b: b["claims"][0].update(unit=None),
    lambda b: b["claims"][0].update(source="seed"),
    lambda b: b["claims"][0].update(paper="wrong-paper"),
    lambda b: b["claim_sources"].clear(),
    lambda b: b["sources"][0].update(evidence_type="abstract"),
    lambda b: b["sources"][0].update(blockers=["Unknown settings"]),
    lambda b: b["claims"][0].update(conditions={"system": "lorenz", "noise": 0.99}),
    lambda b: b["claims"][0].update(method="unsupported"),
    lambda b: b["sources"].append(deepcopy(b["sources"][0])),
])
def test_invalid_evidence_is_rejected(change):
    data = evidence()
    change(data)
    with pytest.raises(ValidationError):
        EvidenceBundle.model_validate(data)


def test_empty_reviewed_bundle_cannot_silently_run_demo(monkeypatch):
    from argparse import Namespace
    from unittest.mock import Mock

    from alloy.agent import loop
    from alloy.cli import run_demo
    from alloy.knowledge.source_bundle import DEFAULT_BUNDLE

    run = Mock()
    monkeypatch.setattr(loop, "investigate", run)
    with pytest.raises(SystemExit, match="No eligible reviewed"):
        run_demo(Namespace(evidence=DEFAULT_BUNDLE, online=False, referee=False))
    run.assert_not_called()


@pytest.mark.parametrize("changes", [
    {"method": "unsupported"},
    {"quantity": "runtime", "unit": "seconds"},
    {"quantity": "coef_error", "unit": "percent"},
    {"conditions": {"system": "pendulum", "noise": 0.1}},
    {"conditions": {"system": "lorenz", "unknown": 42}},
])
def test_reviewed_but_unrunnable_measurements_do_not_become_eligible(changes):
    data = evidence()
    for claim, source in zip(data["claims"], data["sources"], strict=True):
        claim.update(changes)
        source.update(method_family=claim["method"], stated_conditions=claim["conditions"])
    assert not EvidenceBundle.model_validate(data).summary()["eligible_cross_paper_pair"]
