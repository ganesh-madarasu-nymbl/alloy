import pytest

from alloy.knowledge import methods
from alloy.knowledge.bond import Paper
from alloy.knowledge.methods import MethodCandidate, MethodCandidates

SUPPORTED = ("sindy", "smoothed-sindy", "ensemble-sindy", "smoothed-ensemble-sindy")


def test_offline_unknown_weakness_preserves_all_supported_alternatives(monkeypatch):
    monkeypatch.setattr(methods.bond, "search", lambda *_: pytest.fail("offline search must not call Bond"))
    candidates = methods.propose("t_end", "sindy", SUPPORTED + ("ensemble-sindy",), offline=True)
    assert [c.method for c in candidates] == list(SUPPORTED[1:])
    assert all(c.evidence_status == "engineering_hypothesis" for c in candidates)
    assert all(c.source_paper is None and c.source_quote is None for c in candidates)


def test_offline_noise_combination_is_an_unproven_hypothesis():
    candidates = methods.propose("noise", "sindy", SUPPORTED, offline=True)
    combination = next(c for c in candidates if c.method == "smoothed-ensemble-sindy")
    assert combination.evidence_status == "engineering_hypothesis"
    assert combination.source_paper is None
    assert "unproven" in combination.rationale


def test_online_provenance_filters_invalid_citations_and_deduplicates(monkeypatch):
    paper = Paper(id="10.example/ensemble", title="A paper", passages=["Ensembling reduces model variance."])
    monkeypatch.setattr(methods.bond, "search", lambda *_: [paper])
    proposals = [
        # Baselines and unsupported methods cannot get into the experiment queue.
        MethodCandidate(method="sindy", rationale="baseline"),
        MethodCandidate(method="invented-sindy", rationale="unsupported"),
        # Invalid evidence is rejected instead of silently relabelled as an engineering hypothesis.
        MethodCandidate(method="ensemble-sindy", rationale="invented source", evidence_status="source_passage",
                        source_paper="10.example/invented", source_quote="Ensembling reduces model variance."),
        MethodCandidate(method="ensemble-sindy", rationale="wrong quote", evidence_status="source_passage",
                        source_paper=paper.id, source_quote="Ensembling always solves noise."),
        MethodCandidate(method="ensemble-sindy", rationale="source text", evidence_status="source_passage",
                        source_paper=paper.id, source_quote="Ensembling reduces model variance."),
        MethodCandidate(method="ensemble-sindy", rationale="duplicate"),
        MethodCandidate(method="smoothed-ensemble-sindy", rationale="unproven combination"),
    ]
    prompts = []

    def parse(prompt, schema):
        prompts.append(prompt)
        assert schema is MethodCandidates
        return MethodCandidates(candidates=proposals)

    monkeypatch.setattr(methods.llm, "parse", parse)
    found = methods.propose("noise", "sindy", SUPPORTED)
    assert [c.method for c in found] == ["ensemble-sindy", "smoothed-ensemble-sindy"]
    assert found[0].evidence_status == "source_passage"
    assert found[1].evidence_status == "engineering_hypothesis"
    assert paper.id in prompts[0] and paper.passages[0] in prompts[0]


@pytest.mark.parametrize("citation", [
    {"evidence_status": "source_passage"},
    {"source_paper": "paper", "source_quote": " "},
    {"source_quote": "Quoted text."},
    {"source_paper": "paper"},
])
def test_incomplete_citation_is_not_accepted(monkeypatch, citation):
    monkeypatch.setattr(methods.bond, "search", lambda *_: [
        Paper(id="paper", title="Paper", passages=["Quoted text."]),
    ])
    monkeypatch.setattr(methods.llm, "parse", lambda *_: MethodCandidates(candidates=[
        MethodCandidate(method="ensemble-sindy", rationale="test", **citation),
    ]))
    assert methods.propose("noise", "sindy", SUPPORTED) == []


def test_quote_must_belong_to_the_cited_paper(monkeypatch):
    monkeypatch.setattr(methods.bond, "search", lambda *_: [
        Paper(id="paper-a", title="A", passages=["Unrelated passage."]),
        Paper(id="paper-b", title="B", passages=["Quoted text."]),
    ])
    monkeypatch.setattr(methods.llm, "parse", lambda *_: MethodCandidates(candidates=[
        MethodCandidate(method="ensemble-sindy", rationale="wrong attribution", evidence_status="source_passage",
                        source_paper="paper-a", source_quote="Quoted text."),
    ]))
    assert methods.propose("noise", "sindy", SUPPORTED) == []


def test_source_inspiration_does_not_promote_a_combination_to_published_result(monkeypatch):
    monkeypatch.setattr(methods.bond, "search", lambda *_: [
        Paper(id="paper", title="Ensembling", passages=["Ensembling reduces model variance."]),
    ])
    monkeypatch.setattr(methods.llm, "parse", lambda *_: MethodCandidates(candidates=[
        MethodCandidate(method="smoothed-ensemble-sindy", rationale="untested combination inspired by ensembling",
                        source_paper="paper", source_quote="Ensembling reduces model variance."),
    ]))
    found = methods.propose("noise", "sindy", SUPPORTED)
    assert len(found) == 1
    assert found[0].evidence_status == "engineering_hypothesis"


def test_online_search_failure_never_falls_back_to_offline(monkeypatch):
    def fail(*_):
        raise RuntimeError("Bond authorization failed")

    monkeypatch.setattr(methods.bond, "search", fail)
    monkeypatch.setattr(methods.llm, "parse", lambda *_: pytest.fail("must not call the model after search failure"))
    with pytest.raises(RuntimeError, match="Bond authorization failed"):
        methods.propose("noise", "sindy", SUPPORTED)


def test_empty_online_search_does_not_get_offline_prior(monkeypatch):
    monkeypatch.setattr(methods.bond, "search", lambda *_: [])
    monkeypatch.setattr(methods.llm, "parse", lambda *_: MethodCandidates(candidates=[]))
    assert methods.propose("noise", "sindy", SUPPORTED) == []
