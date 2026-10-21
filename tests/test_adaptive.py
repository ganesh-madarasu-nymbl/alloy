import pytest

from alloy.contracts import Budget, ExperimentSpec, RunResult
from alloy.experiments import compare
from alloy.experiments.runner import BudgetExceeded


class FakeRunner:
    def __init__(self, cap, values):
        self.budget = Budget(runs=cap)
        self.values = values
        self.results = []

    def run(self, spec):
        if len(self.results) >= self.budget.runs:
            raise BudgetExceeded()
        r = RunResult(id=str(len(self.results)), spec=spec, metrics={"coef_error": self.values[spec.method]})
        self.results.append(r)
        return r


def specs():
    return {m: ExperimentSpec(task="equations-from-data", adapter="pysindy", method=m) for m in ("a", "b")}


def test_adaptive_empty_incomplete_all_failed_and_nan_have_no_winner():
    assert compare.adaptive(FakeRunner(0, {}), {})[2] is None
    for cap, values in [(0, {"a": 1, "b": 2}), (3, {"a": 1, "b": 2}),
                        (10, {"a": float("inf"), "b": float("nan")})]:
        stats, runs, best = compare.adaptive(FakeRunner(cap, values), specs())
        assert best is None
        assert set(stats) == {"a", "b"}
        assert sum(s["n"] for s in stats.values()) == min(cap, 4)


def test_adaptive_records_drop_counts_and_ties():
    stats, _, best = compare.adaptive(FakeRunner(20, {"a": .1, "b": .9}), specs())
    assert best == "a" and stats["b"]["dropped_after"] == 2
    stats, _, best = compare.adaptive(FakeRunner(20, {"a": .1, "b": .1}), specs())
    assert all(s["n"] == 9 and s["dropped_after"] is None for s in stats.values())
    assert compare.too_close_to_call(stats, best) == ["b"]
    with pytest.raises(ValueError):
        compare.adaptive(FakeRunner(20, {}), specs(), start=0)


def test_nonfinite_hidden_search_cannot_support_positive_conclusion():
    from types import SimpleNamespace

    from alloy.agent.loop import Investigation, _hidden_search
    from alloy.contracts import Claim, Goal

    a = Claim(id="a", paper="synthetic:a", method="a", quantity="coef_error", value=.01)
    b = a.model_copy(update={"id": "b", "value": .9})
    inv = Investigation(id="nan-case", goal=Goal(question="finite evidence required"))
    result = _hidden_search(inv, FakeRunner(4, {"a": float("nan")}), lambda c: specs()["a"], {}, a, b,
                            SimpleNamespace(sweeps={"threshold": [.1]}))
    assert result.verdict.status == "insufficient_evidence"
    assert "finite" in result.verdict.explanation


def test_coatings_caller_handles_empty_comparison_without_division_error(monkeypatch, tmp_path, capsys):
    from dataclasses import replace

    from alloy.cli import run_coatings
    from alloy.config import settings

    monkeypatch.setattr("alloy.cli.settings", replace(settings, run_dir=tmp_path))
    monkeypatch.setattr("alloy.experiments.compare.adaptive", lambda *a, **k: (
        {"single-emitter": {"mean": float("inf"), "stderr": float("inf"), "dropped_after": None}},
        {"single-emitter": []}, None))
    run_coatings(3, 30, 0)
    assert "no best coating" in capsys.readouterr().out
