"""Radiative cooling coatings with the transfer-matrix method.

Goal from the brief: keep cooling power with fewer layers and tolerance to thickness errors.
A coating is a SiO2 emitter on top of alternating TiO2/SiO2 layers on a silver mirror.

Methods:
  single-emitter  one SiO2 layer on silver, thickness from params (default 1000 nm)
  random-search   best of N random stacks, scored at nominal thicknesses
  robust-search   best of N random stacks, scored on average over thickness errors
                  (the combination: random search plus tolerance-aware scoring)

Conditions: n_layers, thickness_tolerance_nm.
Metrics (lower is better): cooling_error at nominal and perturbed_cooling_error under
fabrication errors, where cooling_error = 1 - net cooling power / ideal window emitter power.
"""

from typing import Any

import numpy as np
import tmm

from alloy.contracts import ExperimentSpec
from alloy.experiments.adapters.base import register
from alloy.experiments.data import optics

THICKNESS_NM = {"SiO2": (50.0, 2000.0), "TiO2": (20.0, 200.0)}
PERTURB_SAMPLES = 6


def materials_for(n_layers: int) -> list[str]:
    """Top to bottom: SiO2 emitter, then alternating TiO2/SiO2. The silver mirror is below."""
    return ["SiO2"] + ["TiO2" if i % 2 == 0 else "SiO2" for i in range(n_layers - 1)]


def absorptance(mats: list[str], thick_nm: list[float], um: float) -> float:
    n_list = [1.0] + [optics.MATERIALS[m](um) for m in mats] + [optics.n_ag(um)]
    d_list = [np.inf] + list(thick_nm) + [np.inf]
    reflect = tmm.coh_tmm("s", n_list, d_list, 0, um * 1000)["R"]
    return 1.0 - float(reflect)  # silver substrate is opaque


def performance(mats: list[str], thick_nm: list[float]) -> dict[str, float]:
    solar_w = optics.planck(optics.SOLAR_UM, 5778.0)
    window_w = optics.planck(optics.WINDOW_UM, optics.T_AMBIENT)
    a_solar = np.array([absorptance(mats, thick_nm, um) for um in optics.SOLAR_UM])
    e_window = np.array([absorptance(mats, thick_nm, um) for um in optics.WINDOW_UM])
    alpha = float(np.sum(a_solar * solar_w) / np.sum(solar_w))
    eps = float(np.sum(e_window * window_w) / np.sum(window_w))
    ideal = optics.window_blackbody_power()
    net = eps * ideal - alpha * optics.SOLAR_POWER
    return {
        "solar_absorptance": alpha,
        "window_emissivity": eps,
        "net_cooling_w_m2": net,
        "cooling_error": 1.0 - net / ideal,
    }


class TMMAdapter:
    name = "tmm"
    task = "cooling-coatings"
    methods = ("single-emitter", "random-search", "robust-search")
    condition_keys = ("n_layers", "thickness_tolerance_nm")
    sweeps = {"n_layers": [1, 3, 5], "thickness_tolerance_nm": [0.0, 10.0, 30.0]}

    def _perturbed(self, mats, thick, tol, rng) -> float:
        if tol <= 0:
            return performance(mats, thick)["cooling_error"]
        errs = []
        for _ in range(PERTURB_SAMPLES):
            jitter = np.clip(np.array(thick) + rng.normal(0.0, tol, len(thick)), 1.0, None)
            errs.append(performance(mats, list(jitter))["cooling_error"])
        return float(np.mean(errs))

    def _random_stack(self, mats, rng) -> list[float]:
        return [float(rng.uniform(*THICKNESS_NM[m])) for m in mats]

    def run(self, spec: ExperimentSpec) -> tuple[dict[str, float], dict[str, Any]]:
        cond = spec.conditions
        n_layers = int(cond.get("n_layers", 3))
        tol = float(cond.get("thickness_tolerance_nm", 10.0))
        candidates = int(spec.params.get("candidates", 12))
        rng = np.random.default_rng(spec.seed)

        if spec.method == "single-emitter":
            mats, thick = ["SiO2"], [float(spec.params.get("emitter_nm", 1000.0))]
        elif spec.method in ("random-search", "robust-search"):
            mats = materials_for(n_layers)
            pool = [self._random_stack(mats, rng) for _ in range(candidates)]
            if spec.method == "random-search":
                thick = min(pool, key=lambda t: performance(mats, t)["cooling_error"])
            else:
                thick = min(pool, key=lambda t: self._perturbed(mats, t, tol, np.random.default_rng(spec.seed)))
        else:
            raise ValueError(f"unknown method {spec.method!r}")

        metrics = performance(mats, thick)
        # Score fabrication errors on fresh draws, never the ones robust-search optimized against.
        metrics["perturbed_cooling_error"] = self._perturbed(
            mats, thick, tol, np.random.default_rng(10_000 + spec.seed)
        )
        return metrics, {"layers": [{"material": m, "nm": round(t, 1)} for m, t in zip(mats, thick, strict=True)]}


register(TMMAdapter())
