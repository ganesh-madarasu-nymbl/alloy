"""Controlled comparison: every method sees the same data, seeds and budget."""

from collections import defaultdict
from statistics import mean
from typing import Any

from alloy.contracts import ExperimentSpec, RunResult
from alloy.experiments.runner import Runner


def grid(
    runner: Runner,
    base: ExperimentSpec,
    methods: list[str],
    key: str,
    values: list[Any],
    seeds: list[int],
) -> list[RunResult]:
    """Run every method at every value of the deciding condition, for each seed."""
    results = []
    for method in methods:
        for value in values:
            for seed in seeds:
                spec = base.model_copy(deep=True, update={"method": method, "seed": seed})
                spec.conditions[key] = value
                results.append(runner.run(spec))
    return results


def summarize(results: list[RunResult], key: str, metric: str = "coef_error") -> dict[str, dict[Any, float]]:
    """method -> condition value -> mean metric over seeds (failed runs excluded)."""
    buckets: dict[str, dict[Any, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r in results:
        if r.ok and metric in r.metrics:
            buckets[r.spec.method][r.spec.conditions.get(key)].append(r.metrics[metric])
    return {m: {v: mean(s) for v, s in sorted(by.items())} for m, by in buckets.items()}


def best_method(summary: dict[str, dict[Any, float]], at: Any) -> str | None:
    scored = {m: by[at] for m, by in summary.items() if at in by}
    return min(scored, key=scored.get) if scored else None
