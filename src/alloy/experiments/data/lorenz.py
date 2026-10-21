"""Lorenz system: the supported simulator for the equations-from-data task."""

import numpy as np
from scipy.integrate import solve_ivp

SIGMA, RHO, BETA = 10.0, 28.0, 8.0 / 3.0

# Ground-truth terms keyed by pysindy feature names (x0=x, x1=y, x2=z).
TRUE_TERMS = {
    0: {"x0": -SIGMA, "x1": SIGMA},
    1: {"x0": RHO, "x1": -1.0, "x0 x2": -1.0},
    2: {"x0 x1": 1.0, "x2": -BETA},
}


def rhs(_t, state):
    x, y, z = state
    return [SIGMA * (y - x), x * (RHO - z) - y, x * y - BETA * z]


def simulate(x0=(-8.0, 8.0, 27.0), t_end: float = 10.0, dt: float = 0.002):
    t = np.arange(0.0, t_end, dt)
    sol = solve_ivp(rhs, (t[0], t[-1]), x0, t_eval=t, method="LSODA", rtol=1e-10, atol=1e-10)
    return t, sol.y.T


def true_derivatives(x: np.ndarray) -> np.ndarray:
    return np.array([rhs(0.0, row) for row in x])


NOISE_TYPES = ("gaussian", "outliers")


def add_noise(x: np.ndarray, level: float, rng: np.random.Generator, kind: str = "gaussian") -> np.ndarray:
    """Noise with std = level * (std of each state variable).

    `outliers` adds the same Gaussian noise plus sensor spikes: 1% of samples jump by 20x level.
    """
    if kind not in NOISE_TYPES:
        raise ValueError(f"unknown noise type {kind!r}")
    scale = x.std(axis=0)
    noisy = x + level * scale * rng.standard_normal(x.shape)
    if kind == "outliers":
        spikes = rng.random(x.shape) < 0.01
        noisy += spikes * 20 * level * scale * rng.choice([-1.0, 1.0], size=x.shape)
    return noisy


def true_coefficients(feature_names: list[str]) -> np.ndarray:
    coefs = np.zeros((3, len(feature_names)))
    for row, terms in TRUE_TERMS.items():
        for name, value in terms.items():
            coefs[row, feature_names.index(name)] = value
    return coefs
