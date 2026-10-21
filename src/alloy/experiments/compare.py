"""Controlled comparison: every method sees the same data, seeds and budget."""

from math import isfinite, sqrt
from statistics import mean, stdev

from alloy.contracts import ExperimentSpec, RunResult
from alloy.experiments.runner import BudgetExceeded, Runner


def evaluate(
    runner: Runner, spec: ExperimentSpec, seeds: list[int], metric: str = "coef_error"
) -> tuple[float, float, list[RunResult]]:
    """Run one spec over several seeds. Returns (mean, worst, results); failed runs score inf."""
    results = [runner.run(spec.model_copy(deep=True, update={"seed": s})) for s in seeds]
    scores = [r.metrics.get(metric, float("inf")) if r.ok else float("inf") for r in results]
    return mean(scores), max(scores), results


def best_method(scores: dict[str, float]) -> str | None:
    return min(scores, key=scores.get) if scores else None


def stderr(results: list[RunResult], metric: str = "coef_error") -> float:
    scores = [r.metrics[metric] for r in results if r.ok and metric in r.metrics]
    if len(scores) != len(results) or not all(isfinite(s) for s in scores):
        return float("inf")
    return stdev(scores) / sqrt(len(scores)) if len(scores) > 1 else float("inf")


def too_close_to_call(comparison: dict[str, dict[str, float]], best: str) -> list[str]:
    """Methods whose mean is within the combined standard error of the best one."""
    if best not in comparison or not isfinite(comparison[best]["mean"]):
        return []
    top = comparison[best]
    return [
        m
        for m, s in comparison.items()
        if m != best and isfinite(s["mean"])
        and s["mean"] - top["mean"] <= sqrt(s["stderr"] ** 2 + top["stderr"] ** 2)
    ]


def _stats(results: list[RunResult], metric: str) -> dict[str, float]:
    scores = [r.metrics.get(metric, float("inf")) if r.ok else float("inf") for r in results]
    scores = [s if isfinite(s) else float("inf") for s in scores]
    if not scores:
        return {"mean": float("inf"), "worst": float("inf"), "stderr": float("inf"), "n": 0}
    return {"mean": mean(scores), "worst": max(scores), "stderr": stderr(results, metric), "n": len(scores)}


def adaptive(
    runner: Runner,
    specs: dict[str, ExperimentSpec],
    start: int = 2,
    step: int = 2,
    max_seeds: int = 9,
    z: float = 2.0,
    metric: str = "coef_error",
) -> tuple[dict[str, dict], dict[str, list[RunResult]], str | None]:
    """Race methods: run `start` seeds each, drop any method that is clearly worse than the
    leader (gap > z combined standard errors), add `step` seeds to the rest, stop when one is
    left, the seed cap is reached, or the budget runs out. Survivors besides the leader are ties."""
    if start < 2 or step < 1 or max_seeds < start or not isfinite(z) or z <= 0:
        raise ValueError("race needs start >= 2, step >= 1, max_seeds >= start and positive finite z")
    runs: dict[str, list[RunResult]] = {m: [] for m in specs}
    if not specs:
        return {}, runs, None
    dropped: dict[str, int] = {}

    def add(method: str, upto: int) -> None:
        for seed in range(len(runs[method]), upto):
            runs[method].append(runner.run(specs[method].model_copy(deep=True, update={"seed": seed})))

    alive = list(specs)
    try:
        for seed_count in range(1, start + 1):
            for m in alive:
                add(m, seed_count)
        while True:
            stats = {m: _stats(runs[m], metric) for m in alive}
            leader = min(alive, key=lambda m: stats[m]["mean"])
            top = stats[leader]
            if not isfinite(top["mean"]):
                break
            for m in [m for m in alive if m != leader]:
                s = stats[m]
                gap_se = sqrt(s["stderr"] ** 2 + top["stderr"] ** 2)
                if s["mean"] == float("inf") or s["mean"] - top["mean"] > z * gap_se:
                    alive.remove(m)
                    dropped[m] = s["n"]
            if len(alive) == 1 or all(len(runs[m]) >= max_seeds for m in alive):
                break
            for m in alive:
                add(m, min(len(runs[m]) + step, max_seeds))
    except BudgetExceeded:
        pass  # compare on what we have

    comparison = {m: _stats(rs, metric) | {"dropped_after": dropped.get(m)} for m, rs in runs.items()}
    candidates = [m for m in comparison if m not in dropped and isfinite(comparison[m]["mean"])]
    # A truncated initial round cannot establish a controlled winner over all requested methods.
    leader = (min(candidates, key=lambda m: comparison[m]["mean"])
              if candidates and all(len(rs) >= start for rs in runs.values()) else None)
    return comparison, runs, leader
