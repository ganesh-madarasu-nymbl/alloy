"""Run Brunton et al. 2016 and Kaheman et al. 2020 Lorenz protocols on the PySINDy adapter.

    uv run python scripts/real_pair_probe.py

Settings the papers do not state are marked "assumed". See docs/real-pair-review.md.
"""

from alloy.contracts import ExperimentSpec
from alloy.experiments.adapters import get_adapter

ADAPTER = get_adapter("pysindy")
SEEDS = range(5)
THRESHOLDS = [
    0.01 + i * 0.99 / 99 for i in range(100)
]  # Kaheman: 100 values from 0.01 to 1

BRUNTON = {
    "system": "lorenz",
    "noise_type": "gaussian",
    "noise_scale": "variance",
    "noise_location": "derivative",
    "x0": [-8, 7, 27],
    "dt": 0.001,
    "t_end": 100.0,
    "poly_degree": 5,
    "derivative": "exact",  # assumed
    "threshold": 0.025,  # assumed, from the authors' released code
    "ridge": 0.0,  # Code 1: plain least squares
}
KAHEMAN = {
    "system": "lorenz",
    "noise_type": "gaussian",
    "noise_location": "state",
    "noise_scale": "state_std",
    "x0": [5, 5, 25],
    "dt": 0.01,
    "t_end": 25.0,
    "poly_degree": 2,  # assumed
}


def run(conditions: dict, seed: int = 0) -> dict:
    spec = ExperimentSpec(
        task="equations-from-data",
        adapter="pysindy",
        method="sindy",
        conditions=conditions,
        seed=seed,
    )
    return ADAPTER.run(spec)[0]


def recovered_sets(conditions: dict) -> int:
    """Datasets where any threshold in the sweep gives exactly the true terms (assumed selection rule)."""
    return sum(
        any(run({**conditions, "threshold": t}, s)["recovered"] for t in THRESHOLDS)
        for s in SEEDS
    )


def main() -> None:
    print("Brunton 2016, noise on exact derivatives (eta = noise variance)")
    for eta in (1.0, 10.0):
        m = run({**BRUNTON, "noise": eta})
        print(
            f"  eta {eta:>4}: recovered {m['recovered']:.0f}, coefficient error {m['coef_error']:.4f}"
        )
    m = run({**BRUNTON, "noise": 1.0, "ridge": 0.05})
    print(
        f"  eta  1.0 with pysindy's default ridge 0.05: recovered {m['recovered']:.0f}"
    )

    print("Kaheman 2020, state noise + finite differences: datasets (of 5) recovered")
    for pct in (0.1, 0.25, 0.5, 1.0, 8.0):
        level = (pct / 100) ** 0.5
        print(
            f"  {pct:>5}% read as variance ratio (Eq. 19): {recovered_sets({**KAHEMAN, 'noise': level})}"
        )
    for pct in (2, 4, 6, 8, 10, 12):
        print(
            f"  {pct:>5}% read as std ratio: {recovered_sets({**KAHEMAN, 'noise': pct / 100})}"
        )

    print(
        "Swap the deciding condition: Kaheman data, 8% variance-ratio noise on exact derivatives"
    )
    swapped = {
        **KAHEMAN,
        "noise": 0.08**0.5,
        "noise_location": "derivative",
        "derivative": "exact",
    }
    print(f"  datasets recovered: {recovered_sets(swapped)}")
    print(
        "Swap it the other way: Brunton record, eta = 1 noise on states, finite differences"
    )
    for seed in SEEDS:
        m = run(
            {
                **BRUNTON,
                "noise": 1.0,
                "noise_location": "state",
                "derivative": "numeric",
            },
            seed,
        )
        print(
            f"  seed {seed}: recovered {m['recovered']:.0f}, coefficient error {m['coef_error']:.4f}"
        )


if __name__ == "__main__":
    main()
