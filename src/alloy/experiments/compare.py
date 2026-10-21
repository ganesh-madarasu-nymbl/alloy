"""Controlled comparison: every method sees the same data, seeds and budget."""

from math import sqrt
from statistics import mean, stdev

from alloy.contracts import ExperimentSpec, RunResult
from alloy.experiments.runner import Runner


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
    return stdev(scores) / sqrt(len(scores)) if len(scores) > 1 else float("inf")


def too_close_to_call(comparison: dict[str, dict[str, float]], best: str) -> list[str]:
    """Methods whose mean is within the combined standard error of the best one."""
    top = comparison[best]
    return [
        m
        for m, s in comparison.items()
        if m != best and s["mean"] - top["mean"] <= sqrt(s["stderr"] ** 2 + top["stderr"] ** 2)
    ]
