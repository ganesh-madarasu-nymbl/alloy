"""Equations from noisy data with PySINDy.

Methods map to published approaches:
  sindy                    Brunton, Proctor & Kutz 2016 (finite differences + STLSQ)
  smoothed-sindy           derivative smoothing before regression
  ensemble-sindy           Fasel et al. 2022 (bagged STLSQ)
  smoothed-ensemble-sindy  the combination: smoothing + ensembling
"""

from math import isfinite
from typing import Any

import numpy as np
import pysindy as ps

from alloy.contracts import ExperimentSpec
from alloy.experiments.adapters.base import register
from alloy.experiments.data import lorenz

# Settings where published protocols differ. All optional; the defaults reproduce the original adapter:
# start (-8, 8, 27), degree-2 library, state noise scaled by state std, numeric derivatives, and
# pysindy's default ridge penalty (0.05) inside STLSQ.
PROTOCOL_KEYS = ("x0", "poly_degree", "noise_location", "noise_scale", "derivative", "ensemble_models", "ridge")
PROTOCOL_CHOICES = {
    "noise_location": ("state", "derivative"),
    "noise_scale": lorenz.NOISE_SCALES,
    "derivative": ("numeric", "exact"),
}
DEFAULT_X0 = (-8.0, 8.0, 27.0)
DEFAULT_RIDGE = 0.05


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def _int_in(value: Any, low: int, high: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def protocol_issue(conditions: dict) -> str | None:
    for key, choices in PROTOCOL_CHOICES.items():
        if key in conditions and conditions[key] not in choices:
            return f"{key} must be one of {', '.join(choices)}"
    if not _int_in(conditions.get("poly_degree", 2), 1, 5):
        return "poly_degree must be an integer from 1 to 5"
    if not _int_in(conditions.get("ensemble_models", 20), 2, 200):
        return "ensemble_models must be an integer from 2 to 200"
    ridge = conditions.get("ridge", DEFAULT_RIDGE)
    if not _number(ridge) or ridge < 0:
        return "ridge must be a nonnegative number"
    x0 = conditions.get("x0", DEFAULT_X0)
    if not isinstance(x0, (list, tuple)) or len(x0) != 3 or not all(_number(v) for v in x0):
        return "x0 must be three finite numbers"
    return None


class PySINDyAdapter:
    name = "pysindy"
    task = "equations-from-data"
    methods = ("sindy", "smoothed-sindy", "ensemble-sindy", "smoothed-ensemble-sindy")
    # threshold is a method setting, but papers report it like a condition and it changes results.
    condition_keys = ("system", "noise", "noise_type", "dt", "t_end", "threshold", *PROTOCOL_KEYS)
    # Values to try for a setting a paper never states. Defaults are the first entry's neighbours.
    sweeps = {
        "threshold": [0.05, 0.1, 0.5, 1.0, 2.0],
        "noise_type": ["gaussian", "outliers"],
        "noise": [0.0, 0.05, 0.1, 0.2],
        "dt": [0.001, 0.002, 0.005, 0.01],
        "t_end": [2.0, 5.0, 10.0],
    }

    def _model(
        self,
        method: str,
        threshold: float,
        seed: int,
        degree: int = 2,
        n_models: int = 20,
        ridge: float = DEFAULT_RIDGE,
    ) -> ps.SINDy:
        if method not in self.methods:
            raise ValueError(f"unknown method {method!r}")
        optimizer: Any = ps.STLSQ(threshold=threshold, alpha=ridge)
        if "ensemble" in method:
            np.random.seed(seed)  # EnsembleOptimizer samples with the global RNG
            optimizer = ps.EnsembleOptimizer(opt=optimizer, bagging=True, n_models=n_models)
        diff = ps.SmoothedFiniteDifference() if "smoothed" in method else ps.FiniteDifference()
        return ps.SINDy(
            optimizer=optimizer,
            feature_library=ps.PolynomialLibrary(degree=degree),
            differentiation_method=diff,
        )

    def run(self, spec: ExperimentSpec) -> tuple[dict[str, float], dict[str, Any]]:
        cond = spec.conditions
        if cond.get("system", "lorenz") != "lorenz":
            raise ValueError("only the Lorenz system is supported so far")
        if issue := protocol_issue(cond):
            raise ValueError(issue)
        rng = np.random.default_rng(spec.seed)
        dt, t_end = float(cond.get("dt", 0.002)), float(cond.get("t_end", 10.0))

        _, x = lorenz.simulate(x0=tuple(cond.get("x0", DEFAULT_X0)), t_end=t_end, dt=dt)
        level, kind = float(cond.get("noise", 0.0)), cond.get("noise_type", "gaussian")
        scale = cond.get("noise_scale", "state_std")
        # Brunton et al. 2016 differentiate the clean trajectory exactly and add noise to the derivatives.
        x_dot = lorenz.true_derivatives(x) if cond.get("derivative") == "exact" else None
        if cond.get("noise_location", "state") == "derivative":
            clean_dot = x_dot if x_dot is not None else ps.FiniteDifference()(x, dt)
            x_fit, x_dot = x, lorenz.add_noise(clean_dot, level, rng, kind, scale)
        else:
            x_fit = lorenz.add_noise(x, level, rng, kind, scale)

        threshold = float(cond.get("threshold", spec.params.get("threshold", 0.1)))
        model = self._model(
            spec.method,
            threshold,
            spec.seed,
            cond.get("poly_degree", 2),
            cond.get("ensemble_models", 20),
            float(cond.get("ridge", DEFAULT_RIDGE)),
        )
        model.fit(x_fit, t=dt, x_dot=x_dot)

        names = model.get_feature_names()
        fitted = model.coefficients()
        truth = lorenz.true_coefficients(names)

        # Held-out check on a trajectory from a different start, compared to true derivatives.
        heldout_x0 = cond.get("heldout_x0", (5.0, -6.0, 20.0))
        _, x_test = lorenz.simulate(x0=heldout_x0, t_end=2.0, dt=dt)
        pred, true = model.predict(x_test), lorenz.true_derivatives(x_test)

        support_match = float(np.mean((np.abs(fitted) > 0) == (truth != 0)))
        metrics = {
            "coef_error": float(np.linalg.norm(fitted - truth) / np.linalg.norm(truth)),
            "heldout_error": float(np.linalg.norm(pred - true) / np.linalg.norm(true)),
            "support_match": support_match,
            # Qualitative claims ("recovers the Lorenz equations") read as: exactly the true terms.
            "recovered": float(support_match == 1.0),
        }
        artifacts = {"equations": model.equations(precision=3), "feature_names": names}
        return metrics, artifacts


register(PySINDyAdapter())
