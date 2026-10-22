"""Published SINDy protocols differ in library, start point, noise placement and derivatives."""

from alloy.contracts import Claim, ExperimentSpec
from alloy.experiments.adapters import get_adapter
from alloy.knowledge.source_bundle import execution_issue

BASE = {
    "system": "lorenz",
    "noise": 0.0,
    "noise_type": "gaussian",
    "dt": 0.002,
    "t_end": 10.0,
    "threshold": 0.1,
}


def run(method="sindy", seed=0, **conditions):
    spec = ExperimentSpec(
        task="equations-from-data",
        adapter="pysindy",
        method=method,
        conditions={**BASE, **conditions},
        seed=seed,
    )
    return get_adapter("pysindy").run(spec)


def test_polynomial_degree_sets_the_library():
    _, artifacts = run(poly_degree=3)
    assert (
        len(artifacts["feature_names"]) == 20
    )  # 1 + 3 + 6 + 10 monomials of three states


def test_clean_data_counts_as_recovered():
    metrics, _ = run()
    assert metrics["recovered"] == 1.0


def test_start_point_changes_the_data():
    a, _ = run(noise=0.1, x0=[-8, 7, 27])
    b, _ = run(noise=0.1, x0=[-8, 8, 27])
    assert a["coef_error"] != b["coef_error"]


def test_absolute_noise_scale_differs_from_state_std_scale():
    a, _ = run(noise=0.5, noise_scale="absolute")
    b, _ = run(noise=0.5, noise_scale="state_std")
    assert (
        a["coef_error"] < b["coef_error"]
    )  # state std of Lorenz is about 8, so 0.5 absolute is milder


def test_derivative_noise_with_exact_derivatives_is_far_easier_than_state_noise():
    deriv, _ = run(
        noise=1.0,
        noise_scale="variance",
        noise_location="derivative",
        derivative="exact",
        threshold=0.025,
        dt=0.001,
        poly_degree=5,
    )
    state, _ = run(
        noise=1.0,
        noise_scale="variance",
        noise_location="state",
        threshold=0.025,
        dt=0.001,
        poly_degree=5,
    )
    assert deriv["coef_error"] < 0.05
    assert state["coef_error"] > 4 * deriv["coef_error"]


def claim(**extra):
    return Claim(
        id="c1",
        paper="arxiv:1",
        method="sindy",
        quantity="equations_recovered",
        outcome="recovers",
        conditions={**BASE, **extra},
        quote="q",
        source="manual",
    )


def test_bundle_accepts_explicit_protocol_settings():
    assert (
        execution_issue(
            claim(
                poly_degree=5,
                x0=[-8, 7, 27],
                noise_location="derivative",
                noise_scale="variance",
                derivative="exact",
            )
        )
        is None
    )


def test_bundle_rejects_unknown_or_invalid_protocol_settings():
    assert execution_issue(claim(library="fourier")) is not None
    assert execution_issue(claim(noise_location="parameters")) is not None
    assert execution_issue(claim(poly_degree=0)) is not None
    assert execution_issue(claim(x0=[1, 2])) is not None


BRUNTON_TABLE_4 = {
    "noise": 1.0,
    "noise_scale": "variance",
    "noise_location": "derivative",
    "derivative": "exact",
    "x0": [-8, 7, 27],
    "dt": 0.001,
    "t_end": 100.0,
    "poly_degree": 5,
    "threshold": 0.025,
}


def test_brunton_table_4_recovers_with_or_without_ridge():
    # Brunton's Code 1 uses plain least squares. pysindy's default ridge (0.05) also recovers
    # this setup; an earlier claim that it fails did not reproduce on Windows or Linux CI.
    for ridge in (0.0, 0.05):
        metrics, _ = run(ridge=ridge, **BRUNTON_TABLE_4)
        assert metrics["recovered"] == 1.0 and metrics["coef_error"] < 0.01


def test_bundle_rejects_negative_ridge():
    assert execution_issue(claim(ridge=0.0)) is None
    assert execution_issue(claim(ridge=-1.0)) is not None
