"""MirageLab: challenge a winning method on cases it never saw before."""

from dataclasses import dataclass, field

from alloy.contracts import ExperimentSpec, RunResult
from alloy.experiments.runner import Runner

# Start points and noise levels kept out of the comparison grid.
UNSEEN_CASES = [
    {"heldout_x0": (1.0, 1.0, 1.0), "noise": 0.15},
    {"heldout_x0": (-10.0, -10.0, 30.0), "noise": 0.25},
    {"heldout_x0": (3.0, 15.0, 10.0), "noise": 0.35},
]


@dataclass
class Challenge:
    candidate: str
    baseline: str
    wins: int = 0
    cases: list[dict] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.wins == len(self.cases) and bool(self.cases)


def challenge(
    runner: Runner,
    base: ExperimentSpec,
    candidate: str,
    baseline: str,
    metric: str = "heldout_error",
    cases: list[dict] = UNSEEN_CASES,
) -> Challenge:
    out = Challenge(candidate=candidate, baseline=baseline)
    for i, case in enumerate(cases):
        scores: dict[str, RunResult] = {}
        for method in (candidate, baseline):
            spec = base.model_copy(deep=True, update={"method": method, "seed": 1000 + i})
            spec.conditions.update(case)
            scores[method] = runner.run(spec)
        c, b = (scores[m].metrics.get(metric, float("inf")) for m in (candidate, baseline))
        out.wins += c < b
        out.cases.append({**case, candidate: c, baseline: b, "run_ids": [r.id for r in scores.values()]})
    return out
