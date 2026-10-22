"""Stages 4 to 6 for a real paper pair: once the cause is known, race noise-robust methods on the
failing paper's setup, check the winner on unseen trajectories, and keep the losers.

Every arm is a (method, threshold) pair on the same seeds, so a method is never judged on one
threshold it happens to dislike.
"""

from math import isfinite
from pathlib import Path
from statistics import mean
from typing import Any

from pydantic import BaseModel, Field

from alloy.contracts import ExperimentSpec
from alloy.experiments import compare, verify
from alloy.experiments.runner import BudgetExceeded, Runner
from alloy.memory.deadend import DeadEndMap

METHODS = ("sindy", "smoothed-sindy", "ensemble-sindy", "smoothed-ensemble-sindy")
THRESHOLDS = (0.1, 0.2, 0.5)
BASELINE = "sindy"


class Arm(BaseModel):
    label: str
    method: str
    threshold: float
    mean_error: float
    stderr: float
    seeds: int
    recovered: float
    dropped_after: int | None = None


class FixResult(BaseModel):
    setup: str
    arms: list[Arm] = Field(default_factory=list)
    winner: str | None = None
    baseline: str | None = None
    ties: list[str] = Field(default_factory=list)
    unseen: list[dict[str, Any]] = Field(default_factory=list)
    unseen_wins: int = 0
    dead_ends: list[str] = Field(default_factory=list)
    summary: str = ""

    @property
    def verified(self) -> bool:
        return bool(self.unseen) and self.unseen_wins == len(self.unseen)


def _label(method: str, threshold: float) -> str:
    return f"{method} (threshold {threshold:g})"


def _finite(x: float) -> float | None:
    return x if isfinite(x) else None


def fix(runner: Runner, paper: str, conditions: dict[str, Any], memory: Path | None = None) -> FixResult:
    """Race every method on the failing paper's conditions, then challenge the winner."""
    out = FixResult(setup=paper)
    specs = {
        _label(m, t): ExperimentSpec(
            task="equations-from-data",
            adapter="pysindy",
            method=m,
            conditions={**conditions, "threshold": t},
            seed=0,
        )
        for m in METHODS
        for t in THRESHOLDS
    }
    comparison, runs, leader = compare.adaptive(runner, specs, start=2, step=1, max_seeds=3)
    for label, stats in comparison.items():
        spec = specs[label]
        out.arms.append(
            Arm(
                label=label,
                method=spec.method,
                threshold=spec.conditions["threshold"],
                mean_error=stats["mean"],
                stderr=stats["stderr"],
                seeds=stats["n"],
                recovered=mean(r.metrics.get("recovered", 0.0) for r in runs[label]) if runs[label] else 0.0,
                dropped_after=stats["dropped_after"],
            )
        )
    out.arms.sort(key=lambda a: a.mean_error)
    baselines = [a for a in out.arms if a.method == BASELINE and isfinite(a.mean_error)]
    out.baseline = baselines[0].label if baselines else None
    out.winner = leader
    if leader:
        out.ties = [t for t in compare.too_close_to_call(comparison, leader) if comparison[t]["dropped_after"] is None]

    dead = DeadEndMap(memory) if memory else None
    for arm in out.arms:
        if arm.dropped_after is not None:
            out.dead_ends.append(f"{arm.label}: dropped after {arm.seeds} seeds, error {arm.mean_error:.2f}")
            if dead:
                for r in runs[arm.label]:
                    dead.record(r, f"real pair {paper}: lost the method race to {leader}")

    if leader is None:
        out.summary = "The run budget ran out before every method finished its first seeds, so there is no winner."
        return out
    win = next(a for a in out.arms if a.label == leader)
    base = next((a for a in out.arms if a.label == out.baseline), None)
    if win.method == BASELINE or base is None:
        out.summary = f"No noise-robust variant beat standard SINDy on {paper}'s setup."
        return out
    # An arm dropped early can keep a lower mean than the final leader, and a tie with plain
    # SINDy is no win either: say so instead of claiming an improvement.
    if win.mean_error >= base.mean_error or any(t.startswith(f"{BASELINE} (") for t in out.ties):
        out.summary = (
            f"No noise-robust variant clearly beat standard SINDy on {paper}'s setup: {leader} reached "
            f"coefficient error {win.mean_error:.2f} against {base.mean_error:.2f} for {out.baseline}, "
            "within seed noise or worse."
        )
        return out

    try:
        for i, case in enumerate(verify.unseen_cases("noise", conditions.get("noise", 0.0))):
            row: dict[str, Any] = {
                "start": case["heldout_x0"],
                "noise": case.get("noise", conditions.get("noise")),
            }
            for label in (leader, out.baseline):
                spec = specs[label].model_copy(deep=True, update={"seed": 1000 + i})
                spec.conditions.update(case)
                r = runner.run(spec)
                row[label] = _finite(r.metrics.get("heldout_error", float("inf"))) if r.ok else None
            c, b = row[leader], row[out.baseline]
            row["winner_better"] = c is not None and b is not None and c < b
            out.unseen_wins += row["winner_better"]
            out.unseen.append(row)
    except BudgetExceeded:
        pass  # report the cases that ran

    recovers = "recovers the exact Lorenz terms" if win.recovered >= 0.5 else "still misses some Lorenz terms"
    out.summary = (
        f"On {paper}'s setup, {leader} cuts coefficient error from {base.mean_error:.2f} "
        f"(best standard SINDy, {out.baseline}) to {win.mean_error:.2f}, and {recovers}. "
        f"It beats standard SINDy on {out.unseen_wins} of {len(out.unseen)} unseen trajectories."
    )
    if out.ties:
        out.summary += f" Tied within seed noise: {', '.join(out.ties)}."
    return out
