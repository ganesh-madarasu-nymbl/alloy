"""Benchmark: score Alloy and the plain agent on the same scenarios with the same budget.

A system scores on three things:
  cause    did it name the condition that actually causes the gap (scenario truth)
  answer   is its recommended method within tolerance of the best method, measured by an
           oracle on 10 seeds that neither system ever sees
  cost     runs used
"""

import json
from pathlib import Path
from statistics import mean
from typing import Any

from pydantic import BaseModel

from alloy.contracts import Claim, ExperimentSpec
from alloy.experiments.adapters import get_adapter

SCENARIO_DIR = Path(__file__).resolve().parents[2] / "data" / "scenarios"
ORACLE_SEEDS = range(100, 110)
REL_TOL, ABS_TOL = 0.10, 0.02  # answer counts as correct within either tolerance of the oracle best


class Scenario(BaseModel):
    name: str
    question: str
    claims: list[Claim]
    truth: dict[str, Any]
    note: str = ""


class Oracle(BaseModel):
    hard_conditions: dict[str, Any]
    means: dict[str, float]
    acceptable: list[str]


class Score(BaseModel):
    system: str
    scenario: str
    cause: str | None
    cause_correct: bool
    answer: str | None
    answer_correct: bool
    answer_oracle_error: float | None
    runs_used: int


def load_scenarios(names: list[str] | None = None) -> list[Scenario]:
    paths = sorted(SCENARIO_DIR.glob("*.json"))
    scenarios = [Scenario(**json.loads(p.read_text(encoding="utf-8"))) for p in paths]
    return [s for s in scenarios if not names or s.name in names]


def oracle(scenario: Scenario, adapter_name: str = "pysindy", task: str = "equations-from-data") -> Oracle:
    adapter = get_adapter(adapter_name)

    def mean_error(method: str, conds: dict) -> float:
        errs = []
        for seed in ORACLE_SEEDS:
            spec = ExperimentSpec(task=task, adapter=adapter_name, method=method, conditions=conds, seed=seed)
            errs.append(adapter.run(spec)[0]["coef_error"])
        return mean(errs)

    method = scenario.claims[0].method
    hard = max((c.conditions for c in scenario.claims), key=lambda conds: mean_error(method, conds))
    means = {m: mean_error(m, hard) for m in adapter.methods}
    best = min(means.values())
    acceptable = [m for m, v in means.items() if v <= max(best * (1 + REL_TOL), best + ABS_TOL)]
    return Oracle(hard_conditions=hard, means=means, acceptable=acceptable)


def score(system: str, scenario: Scenario, truth: Oracle, cause: str | None, answer: str | None, runs: int) -> Score:
    return Score(
        system=system,
        scenario=scenario.name,
        cause=cause,
        cause_correct=cause == scenario.truth["deciding_condition"],
        answer=answer,
        answer_correct=answer in truth.acceptable,
        answer_oracle_error=truth.means.get(answer) if answer else None,
        runs_used=runs,
    )
