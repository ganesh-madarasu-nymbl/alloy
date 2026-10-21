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
