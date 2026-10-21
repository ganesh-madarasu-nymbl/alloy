from alloy.agent.baseline import runs_to_target
from alloy.contracts import ExperimentSpec, RunResult


def result(i, noise, err, ok=True):
    spec = ExperimentSpec(task="t", adapter="pysindy", method="m", conditions={"noise": noise})
    return RunResult(id=f"r{i}", spec=spec, metrics={"coef_error": err}, ok=ok)


def test_runs_to_target_counts_first_hit_at_hard_condition():
    runs = [result(1, 0.01, 0.0), result(2, 0.2, 0.9), result(3, 0.2, 0.3, ok=False), result(4, 0.2, 0.2)]
    assert runs_to_target(runs, "noise", 0.2, target=0.3) == 4
    assert runs_to_target(runs, "noise", 0.2, target=0.1) is None
