"""Bounded experiment runner. Every run counts against one budget and is logged to disk."""

import json
import time
import uuid
from pathlib import Path

from alloy.contracts import Budget, ExperimentSpec, RunResult
from alloy.experiments.adapters import get_adapter


class BudgetExceeded(RuntimeError):
    pass


class Runner:
    def __init__(self, budget: Budget, run_dir: Path):
        self.budget = budget
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.results: list[RunResult] = []
        self._started = time.monotonic()

    @property
    def runs_used(self) -> int:
        return len(self.results)

    @property
    def minutes_used(self) -> float:
        return (time.monotonic() - self._started) / 60

    def run(self, spec: ExperimentSpec) -> RunResult:
        if self.runs_used >= self.budget.runs:
            raise BudgetExceeded(f"run budget of {self.budget.runs} used up")
        if self.minutes_used >= self.budget.minutes:
            raise BudgetExceeded(f"time budget of {self.budget.minutes} min used up")

        result = RunResult(id=f"r{self.runs_used + 1:03d}-{uuid.uuid4().hex[:6]}", spec=spec)
        start = time.perf_counter()
        try:
            result.metrics, result.artifacts = get_adapter(spec.adapter).run(spec)
        except Exception as exc:  # noqa: BLE001 - a failed run is a result too; it goes to the Dead-End Map
            result.ok, result.error = False, f"{type(exc).__name__}: {exc}"
        result.seconds = time.perf_counter() - start

        self.results.append(result)
        (self.run_dir / f"{result.id}.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
        return result

    def save_manifest(self) -> Path:
        path = self.run_dir / "manifest.json"
        path.write_text(json.dumps([r.model_dump() for r in self.results], indent=2, default=str), encoding="utf-8")
        return path
