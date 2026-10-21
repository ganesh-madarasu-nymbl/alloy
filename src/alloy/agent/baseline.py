"""Plain research-and-coding agent: the fair comparison for the pitch.

The baseline gets the same claims (as text), the same adapter (as a tool) and the same Budget as
Alloy, but no evidence graph, no Condition Check and no method search. We count the runs each
side needs to first reach a target error at the hard condition.
"""

import json
from pathlib import Path

from anthropic import beta_tool
from pydantic import BaseModel, Field

from alloy import llm
from alloy.config import settings
from alloy.contracts import Budget, Claim, ExperimentSpec, Goal, RunResult
from alloy.experiments.adapters import get_adapter
from alloy.experiments.runner import BudgetExceeded, Runner

MAX_TURNS = 40

SYSTEM = """You are a research engineer with a simulator tool. Work out why the papers below
disagree and find the method that recovers the equations best under the harder condition.
Each run costs budget, so plan before you run. When you are done, call submit."""


class BaselineResult(BaseModel):
    runs_used: int
    runs_to_target: int | None = Field(description="1-based index of the first run that hit the target")
    best_error: float | None
    submitted_method: str | None
    submitted_reason: str | None
    turns: int
    input_tokens: int
    output_tokens: int


def runs_to_target(results: list[RunResult], key: str, hard_value, target: float) -> int | None:
    for i, r in enumerate(results, start=1):
        if r.ok and r.spec.conditions.get(key) == hard_value and r.metrics.get("coef_error", 1e9) <= target:
            return i
    return None


def _claims_text(claims: list[Claim]) -> str:
    return "\n".join(
        f"- {c.title} ({c.paper}): {c.method} {c.outcome or c.value} on {c.quantity}; "
        f"conditions {json.dumps(c.conditions)}"
        for c in claims
    )


def run_baseline(
    goal: Goal,
    claims: list[Claim],
    key: str,
    hard_value,
    target: float,
    run_dir: Path,
) -> BaselineResult:
    adapter = get_adapter(goal.adapter)
    runner = Runner(Budget(**goal.budget.model_dump()), run_dir)
    submitted: dict = {}

    @beta_tool
    def run_experiment(method: str, noise: float, seed: int = 0) -> str:
        """Run one simulation fit and return its metrics as JSON.

        Args:
            method: One of the supported methods listed in the task.
            noise: Measurement noise level as a fraction of signal std, e.g. 0.05.
            seed: Random seed for the noise.
        """
        spec = ExperimentSpec(task=goal.task, adapter=goal.adapter, method=method,
                              conditions={"system": "lorenz", "noise": noise}, seed=seed)
        try:
            result = runner.run(spec)
        except BudgetExceeded as exc:
            return json.dumps({"error": str(exc)})
        if not result.ok:
            return json.dumps({"error": result.error})
        left = goal.budget.runs - runner.runs_used
        return json.dumps({"run_id": result.id, "metrics": result.metrics, "runs_left": left})

    @beta_tool
    def submit(method: str, reason: str) -> str:
        """Submit your final answer and stop.

        Args:
            method: The method you recommend under the harder condition.
            reason: One or two sentences on why the papers disagree and why this method wins.
        """
        submitted.update(method=method, reason=reason)
        return "submitted"

    prompt = (
        f"Goal: {goal.question}\n\nPapers:\n{_claims_text(claims)}\n\n"
        f"Supported methods: {', '.join(adapter.methods)}\n"
        f"Metric: coef_error (lower is better). Budget: {goal.budget.runs} runs."
    )
    runner_loop = llm.client().beta.messages.tool_runner(
        model=settings.model,
        max_tokens=16000,
        system=SYSTEM,
        output_config={"effort": "medium"},
        tools=[run_experiment, submit],
        messages=[{"role": "user", "content": prompt}],
    )

    turns = input_tokens = output_tokens = 0
    for message in runner_loop:
        turns += 1
        input_tokens += message.usage.input_tokens
        output_tokens += message.usage.output_tokens
        if message.stop_reason == "refusal":
            raise llm.LLMRefusal("baseline agent declined")
        if submitted or turns >= MAX_TURNS:
            break

    runner.save_manifest()
    hard = [r.metrics["coef_error"] for r in runner.results
            if r.ok and r.spec.conditions.get(key) == hard_value]
    result = BaselineResult(
        runs_used=runner.runs_used,
        runs_to_target=runs_to_target(runner.results, key, hard_value, target),
        best_error=min(hard) if hard else None,
        submitted_method=submitted.get("method"),
        submitted_reason=submitted.get("reason"),
        turns=turns,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    (Path(run_dir) / "baseline.json").write_text(result.model_dump_json(indent=2))
    return result
