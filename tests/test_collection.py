import random

import pytest

from alloy.contracts import Claim
from alloy.knowledge.collection import canonical_work, plan_collection


def claims3():
    return [Claim(id=str(i), paper=f"10.1234/work{i}", method="sindy", quantity="coef_error", unit="relative",
                  value=value, conditions={"system": "lorenz", "noise": noise}, source="seed")
            for i, value, noise in [(1, .01, .01), (2, .5, .1), (3, .9, .2)]]


@pytest.mark.parametrize("a,b", [
    ("https://doi.org/10.1234/ABC", "doi:10.1234/abc"),
    ("https://arxiv.org/pdf/1509.03580v2.pdf", "arXiv:1509.03580"),
    ("arxiv:math/0301001v3", "https://arxiv.org/abs/math/0301001"),
    ("doi:10.1073/pnas.1517384113", "https://doi.org/10.1073/pnas.1517384113?utm_source=review#section"),
    ("arxiv:1509.03580", "https://arxiv.org/abs/1509.03580v2?context=math"),
])
def test_known_identity_aliases(a, b):
    assert canonical_work(a) == canonical_work(b)


def test_queue_order_invariance_coverage_and_visible_dispositions():
    claims = claims3()
    expected = plan_collection(claims, max_audits=2)
    for i in range(8):
        random.Random(i).shuffle(claims)
        assert plan_collection(claims, max_audits=2) == expected
    assert len(expected.selected) == 2
    selected = [p for p in expected.pairs if p.id in expected.selected]
    assert len({c for p in selected for c in p.claims}) == 3
    assert any(p.disposition == "deferred" for p in expected.pairs)
    assert all(p.ranking_reasons for p in selected)


def test_aliases_are_never_independent_evidence_and_ambiguous_ids_stay_visible():
    a, b, c = claims3()
    b.paper = "https://doi.org/10.1234/WORK1"
    c.paper = "unresolved-work"
    plan = plan_collection([a, b, c])
    assert plan.pairs[0].disposition == "incompatible"
    assert "same canonical work" in plan.pairs[0].reasons[0]
    assert plan.identity_warnings


@pytest.mark.parametrize("field,value,disposition", [
    ("unit", "percent", "incompatible"), ("method", "unknown", "incompatible"),
    ("quantity", "runtime", "incompatible"), ("conditions", {"system": "rossler"}, "blocked_evidence"),
    ("conditions", {"system": "lorenz", "noise": None}, "blocked_evidence"),
    ("conditions", {"system": "lorenz", "noise": .1, "madeup": 1}, "blocked_evidence"),
    ("conditions", {"system": "lorenz", "noise": -.1}, "blocked_evidence"),
    ("source", "manual", "blocked_evidence"),
])
def test_unsafe_pairs_never_selected(field, value, disposition):
    a, b, _ = claims3()
    b = b.model_copy(update={field: value})
    plan = plan_collection([a, b])
    assert not plan.selected
    assert plan.pairs[0].disposition == disposition


def test_limits_empty_and_no_detected_gap():
    assert not plan_collection([]).selected
    a, b, _ = claims3()
    b.value = a.value
    assert plan_collection([a, b]).pairs[0].disposition == "no_detected_discrepancy"
    with pytest.raises(ValueError, match="unique"):
        plan_collection([a, a])
    with pytest.raises(ValueError, match="20"):
        plan_collection([a.model_copy(update={"id": str(i), "paper": f"work{i}"}) for i in range(21)])
    with pytest.raises(ValueError, match="100"):
        plan_collection([a.model_copy(update={"id": str(i)}) for i in range(101)])


def test_saved_plan_references_cannot_be_changed():
    from alloy.knowledge.collection import CollectionPlan

    raw = plan_collection(claims3()).model_dump()
    raw["pairs"][0]["claims"] = ["1", "missing"]
    with pytest.raises(ValueError):
        CollectionPlan.model_validate(raw)


def test_finite_extreme_values_do_not_overflow_screening():
    from alloy.knowledge.collection import CollectionPlan

    a, b, _ = claims3()
    a.value, b.value = 1e308, -1e308
    plan = plan_collection([a, b])
    assert plan.pairs[0].gap == 2
    assert CollectionPlan.model_validate_json(plan.model_dump_json()) == plan


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_input_rejected_before_lossy_json_export(value):
    a, b, _ = claims3()
    with pytest.raises(ValueError, match="finite"):
        plan_collection([a, b.model_copy(update={"value": value})])
    with pytest.raises(ValueError, match="finite"):
        plan_collection([a, b.model_copy(update={"conditions": {"system": "lorenz", "noise": value}})])
