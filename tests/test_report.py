import pytest

from alloy.agent.loop import Investigation
from alloy.contracts import Claim, Goal, Verdict
from alloy.experiments.report import to_markdown, write


def investigation():
    return Investigation(id="audit-test", goal=Goal(question="Why do the measurements differ?"))


def test_partial_seed_report_does_not_present_placeholders_as_published_evidence():
    inv = investigation()
    inv.claims = [Claim(
        id="zero", paper="10.1234/zero", method="sindy", quantity="coef_error", value=0.0,
        unit="relative", outcome="exact recovery", quote="PLACEHOLDER: insert paper passage", source="seed",
    )]
    text = to_markdown(inv)
    assert "Partial record: no verdict recorded" in text
    assert "seed or placeholder claims are not published evidence" in text
    assert "[10.1234/zero](https://doi.org/10.1234/zero)" in text
    assert "0.0 | relative | exact recovery" in text
    assert "Source: seed" in text and "> PLACEHOLDER: insert paper passage" in text
    assert "No replay notebook is recorded" in text


def test_populated_audit_preserves_results_and_provenance_caveats(tmp_path):
    inv = investigation()
    inv.runs_used = 12
    inv.claims = [Claim(
        id="a", paper="arxiv:2111.10992", method="sindy", quantity="coef_error", value=0.2,
        unit="relative", conditions={"noise": 0.1}, quote="Error | at noise 0.1 is 0.2.", source="manual",
    )]
    inv.conflict = ("a", "b")
    inv.condition_report = {"comparable": True, "differing": {"noise": [0.1, 0.2]}, "notes": ["Review settings"]}
    inv.reproduction = {"a": {"conditions": {"noise": 0.1}, "coef_error": 0.2, "run_ids": ["run-a"]}}
    inv.attribution = {"noise": 0.3}
    inv.hidden_search = [{"condition": "threshold", "value": 1.0, "coef_error": 0.8, "miss": 0.1}]
    inv.candidates = [
        {"method": "ensemble-sindy", "rationale": "Try bagging", "evidence_status": "source_passage",
         "source_paper": "arxiv:2111.10992", "source_quote": "Ensembling reduces variance."},
        {"method": "smoothed-ensemble-sindy", "rationale": "Untested combination",
         "evidence_status": "engineering_hypothesis"},
    ]
    inv.comparison = {"ensemble-sindy": {"mean": 0.1, "worst": 0.2, "stderr": 0.01}}
    inv.challenge = {"candidate": "ensemble-sindy", "baseline": "sindy",
                     "cases": [{"noise": 0.15, "ensemble-sindy": 0.08, "sindy": 0.3, "run_ids": ["unseen-a"]}]}
    inv.referee = ["Only one metric was compared."]
    inv.notebook = str(tmp_path / "replay.ipynb")
    inv.verdict = Verdict(question=inv.goal.question, status="likely_unstated_cause",
                          explanation="Confirm threshold with the authors.")
    opinion = {"agent_cause": "noise", "alloy_cause": "threshold", "cause_agrees": False,
               "agent_method": "sindy", "alloy_method": "ensemble-sindy", "method_agrees": False,
               "agent_runs": 9, "agent_reason": "The plain agent's original reason."}
    path = write(inv, tmp_path, opinion)
    text = path.read_text()
    assert path.name == "audit.md" and text == to_markdown(inv, opinion)
    for expected in ["likely unstated cause", "12 of 60", "run-a", "Review settings", "0.15", "0.08",
                     "Ensembling reduces variance.", "Try bagging", "Untested combination", "0.01",
                     "Only one metric was compared.", "The plain agent's original reason."]:
        assert expected in text
    assert "[arxiv:2111.10992](https://arxiv.org/abs/2111.10992)" in text
    assert "quote occurrence" in text and "not scientific validation" in text
    assert "can miss interactions" in text and "ask the authors to confirm" in text
    assert "seed or placeholder" not in text


@pytest.mark.parametrize("challenge", [
    {"cases": [{"noise": 0.1, "sindy": 0.4}]},
    {"candidate": "ensemble-sindy", "baseline": "sindy", "cases": [{"noise": 0.2, "sindy": 0.5}]},
    {"candidate": [], "baseline": None, "cases": [None, "unfinished", {}]},
    {"cases": None},
])
def test_partial_challenge_and_optional_records_render_without_crashing(challenge):
    inv = investigation()
    inv.challenge = challenge
    inv.conflict = ("a", "b")
    inv.condition_report = {"notes": None}
    inv.reproduction = {"a": {"coef_error": 0.0}}
    inv.hidden_search = [{}]
    inv.candidates = [{"method": "ensemble-sindy"}]
    inv.comparison = {"sindy": {}}
    text = to_markdown(inv, {"agent_cause": "noise"})
    assert "Unseen cases" in text and "not recorded" in text
    assert "unknown (legacy record)" in text
    assert "Partial record: no verdict recorded" in text


def test_unknown_paper_identifier_does_not_become_an_external_link():
    inv = investigation()
    inv.claims = [Claim(id="a", paper="javascript:alert(1)", method="sindy", quantity="error",
                        quote="Quoted result.", source="manual")]
    text = to_markdown(inv)
    assert "javascript:alert(1)" in text
    assert "](javascript:" not in text
