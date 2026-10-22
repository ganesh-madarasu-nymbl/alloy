from types import SimpleNamespace
from unittest.mock import Mock

from alloy.agent.loop import Investigation, _run
from alloy.contracts import Claim, Goal


def test_loop_never_compares_runtime_to_coefficient_error(tmp_path, monkeypatch):
    claims = [Claim(id=f"c{i}", paper=f"p{i}", method="sindy", quantity="runtime", value=v,
                    unit="seconds", conditions={"system": "lorenz"}) for i, v in enumerate((1, 10))]
    adapter = SimpleNamespace(condition_keys=("system", "noise"), methods=("sindy",), name="pysindy")
    runner = Mock()
    evaluate = Mock()
    monkeypatch.setattr("alloy.agent.loop.compare.evaluate", evaluate)
    inv = Investigation(id="metric-guard", goal=Goal(question="test"))
    _run(inv, True, claims, None, runner, adapter, Mock(), tmp_path)
    assert inv.verdict.status == "insufficient_evidence"
    assert "coef_error" in inv.skipped[0]
    evaluate.assert_not_called()


def test_online_loop_skips_papers_whose_claims_fail_evidence_gates(tmp_path, monkeypatch):
    papers = [SimpleNamespace(id="bad"), SimpleNamespace(id="good")]
    good = Claim(id="c1", paper="good", method="sindy", quantity="coef_error", value=0.1,
                 conditions={"system": "lorenz"})

    def extract(paper, keys, start=1):
        if paper.id == "bad":
            raise ValueError("bad: claim value is not a finite number")
        return [good]

    monkeypatch.setattr("alloy.agent.loop.bond.search", lambda q: papers)
    monkeypatch.setattr("alloy.agent.loop.extract_claims", extract)
    adapter = SimpleNamespace(condition_keys=("system", "noise"), methods=("sindy",), name="pysindy")
    inv = Investigation(id="extract-guard", goal=Goal(question="test"))
    _run(inv, False, [], None, Mock(), adapter, Mock(), tmp_path)
    assert inv.claims == [good]
    assert inv.skipped[0] == "bad: claims rejected (bad: claim value is not a finite number)"
