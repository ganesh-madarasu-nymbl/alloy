"""MirageLab: challenge a winning method on cases it never saw before."""

from dataclasses import dataclass, field
from typing import Any

from alloy.contracts import ExperimentSpec, RunResult
from alloy.experiments.runner import Runner

UNSEEN_STARTS = [(1.0, 1.0, 1.0), (-10.0, -10.0, 30.0), (3.0, 15.0, 10.0)]
SHIFTS = [0.75, 1.0, 1.25]  # nudge the deciding condition around the hard value


def unseen_cases(key: str, hard_value: Any) -> list[dict]:
    """New start points, with the deciding condition nudged when it is numeric."""
    cases = []
    for x0, shift in zip(UNSEEN_STARTS, SHIFTS, strict=True):
        case: dict[str, Any] = {"heldout_x0": x0}
        if isinstance(hard_value, int | float) and not isinstance(hard_value, bool):
            case[key] = hard_value * shift
        cases.append(case)
    return cases


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
    cases: list[dict],
    metric: str = "heldout_error",
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
