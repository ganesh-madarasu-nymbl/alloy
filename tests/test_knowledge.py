from alloy.contracts import Claim
from alloy.knowledge import conditions
from alloy.knowledge.graph import EvidenceGraph


def test_seed_claims_conflict(seed_claims):
    graph = EvidenceGraph()
    graph.add_claims(seed_claims)
    pairs = graph.conflicts()
    assert [(a.id, b.id) for a, b in pairs] == [("c1", "c2")]


def test_graph_round_trip(seed_claims, tmp_path):
    graph = EvidenceGraph()
    graph.add_claims(seed_claims)
    loaded = EvidenceGraph.load(graph.save(tmp_path / "g.json"))
    assert {c.id for c in loaded.claims} == {"c1", "c2"}


def test_condition_check_finds_noise(seed_claims):
    a, b = seed_claims
    report = conditions.check(a, b, adapter_keys=("system", "noise"))
    assert report.comparable
    assert report.shared == {"system": "lorenz"}
    assert report.reproducible == ["noise"]


def test_different_quantities_are_not_comparable():
    a = Claim(id="a", paper="p", method="m", quantity="coef_error", value=0.1)
    b = Claim(id="b", paper="q", method="m", quantity="runtime", value=9.0)
    assert not conditions.check(a, b).comparable
