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
