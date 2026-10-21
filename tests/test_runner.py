import pytest

from alloy.contracts import Budget, ExperimentSpec
from alloy.experiments.runner import BudgetExceeded, Runner
from alloy.memory.deadend import DeadEndMap

SPEC = ExperimentSpec(task="equations-from-data", adapter="pysindy", method="sindy", conditions={"noise": 0.0})


def test_budget_is_enforced(tmp_path):
    runner = Runner(Budget(runs=1), tmp_path)
    runner.run(SPEC)
    with pytest.raises(BudgetExceeded):
        runner.run(SPEC)


def test_failed_run_is_recorded_not_raised(tmp_path):
    runner = Runner(Budget(runs=2), tmp_path)
    result = runner.run(SPEC.model_copy(update={"method": "no-such-method"}))
    assert not result.ok and "no-such-method" in result.error
    assert (tmp_path / f"{result.id}.json").exists()


def test_dead_end_lookup(tmp_path):
    runner = Runner(Budget(runs=1), tmp_path)
    result = runner.run(SPEC.model_copy(update={"method": "no-such-method"}))
    deadends = DeadEndMap(tmp_path / "deadends.jsonl")
    deadends.record(result, "run failed")
    assert len(deadends.lookup("no-such-method", noise=0.0)) == 1
    assert deadends.lookup("sindy") == []
