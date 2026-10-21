"""Controlled comparison: every method sees the same data, seeds and budget."""

from statistics import mean

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
