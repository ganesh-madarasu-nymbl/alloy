from alloy.contracts import ExperimentSpec
from alloy.experiments.adapters import get_adapter


def run(method, noise, seed=0):
    spec = ExperimentSpec(
        task="equations-from-data", adapter="pysindy", method=method, conditions={"noise": noise}, seed=seed
    )
    metrics, _ = get_adapter("pysindy").run(spec)
    return metrics


def test_recovers_lorenz_from_clean_data():
    assert run("sindy", 0.0)["coef_error"] < 0.01


def test_noise_breaks_plain_sindy():
    assert run("sindy", 0.2)["coef_error"] > 0.5


def test_smoothing_helps_at_high_noise():
    assert run("smoothed-sindy", 0.2)["coef_error"] < run("sindy", 0.2)["coef_error"]
