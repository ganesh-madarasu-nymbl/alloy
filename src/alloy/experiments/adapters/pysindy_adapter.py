"""Equations from noisy data with PySINDy.

Methods map to published approaches:
  sindy                    Brunton, Proctor & Kutz 2016 (finite differences + STLSQ)
  smoothed-sindy           derivative smoothing before regression
  ensemble-sindy           Fasel et al. 2022 (bagged STLSQ)
  smoothed-ensemble-sindy  the combination: smoothing + ensembling
"""

from typing import Any

import numpy as np
import pysindy as ps

from alloy.contracts import ExperimentSpec
from alloy.experiments.adapters.base import register
from alloy.experiments.data import lorenz


class PySINDyAdapter:
    name = "pysindy"
    task = "equations-from-data"
    methods = ("sindy", "smoothed-sindy", "ensemble-sindy", "smoothed-ensemble-sindy")
    # threshold is a method setting, but papers report it like a condition and it changes results.
    condition_keys = ("system", "noise", "noise_type", "dt", "t_end", "threshold")
    # Values to try for a setting a paper never states. Defaults are the first entry's neighbours.
    sweeps = {
        "threshold": [0.05, 0.1, 0.5, 1.0, 2.0],
        "noise_type": ["gaussian", "outliers"],
        "noise": [0.0, 0.05, 0.1, 0.2],
        "dt": [0.001, 0.002, 0.005, 0.01],
        "t_end": [2.0, 5.0, 10.0],
    }

    def _model(self, method: str, threshold: float, seed: int) -> ps.SINDy:
        if method not in self.methods:
            raise ValueError(f"unknown method {method!r}")
        optimizer: Any = ps.STLSQ(threshold=threshold)
        if "ensemble" in method:
            np.random.seed(seed)  # EnsembleOptimizer samples with the global RNG
            optimizer = ps.EnsembleOptimizer(opt=optimizer, bagging=True, n_models=20)
        diff = ps.SmoothedFiniteDifference() if "smoothed" in method else ps.FiniteDifference()
        return ps.SINDy(
            optimizer=optimizer,
            feature_library=ps.PolynomialLibrary(degree=2),
            differentiation_method=diff,
        )

    def run(self, spec: ExperimentSpec) -> tuple[dict[str, float], dict[str, Any]]:
        cond = spec.conditions
        if cond.get("system", "lorenz") != "lorenz":
            raise ValueError("only the Lorenz system is supported so far")
        rng = np.random.default_rng(spec.seed)
        dt, t_end = float(cond.get("dt", 0.002)), float(cond.get("t_end", 10.0))

        _, x = lorenz.simulate(t_end=t_end, dt=dt)
        x_noisy = lorenz.add_noise(x, float(cond.get("noise", 0.0)), rng, cond.get("noise_type", "gaussian"))

        threshold = float(cond.get("threshold", spec.params.get("threshold", 0.1)))
        model = self._model(spec.method, threshold, spec.seed)
        model.fit(x_noisy, t=dt)

        names = model.get_feature_names()
        fitted = model.coefficients()
        truth = lorenz.true_coefficients(names)

        # Held-out check on a trajectory from a different start, compared to true derivatives.
        heldout_x0 = cond.get("heldout_x0", (5.0, -6.0, 20.0))
        _, x_test = lorenz.simulate(x0=heldout_x0, t_end=2.0, dt=dt)
        pred, true = model.predict(x_test), lorenz.true_derivatives(x_test)

        metrics = {
            "coef_error": float(np.linalg.norm(fitted - truth) / np.linalg.norm(truth)),
            "heldout_error": float(np.linalg.norm(pred - true) / np.linalg.norm(true)),
            "support_match": float(np.mean((np.abs(fitted) > 0) == (truth != 0))),
        }
        artifacts = {"equations": model.equations(precision=3), "feature_names": names}
        return metrics, artifacts


register(PySINDyAdapter())
