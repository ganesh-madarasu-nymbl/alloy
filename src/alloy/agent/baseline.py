"""Plain research-and-coding agent: the fair comparison for the pitch.

The baseline gets the same claims (as text), the same adapter (as a tool) and the same Budget as
Alloy, but no evidence graph, no Condition Check and no method search. bench.py scores both.
"""

import json
from pathlib import Path

from pydantic import BaseModel

from alloy import llm
from alloy.config import settings
from alloy.contracts import Budget, Claim, ExperimentSpec, Goal
from alloy.experiments.adapters import get_adapter
from alloy.experiments.runner import BudgetExceeded, Runner

MAX_TURNS = 40

SYSTEM = """You are a research engineer with a simulator tool. Work out which condition causes
the papers below to disagree, and find the method that recovers the equations best under the
harder paper's setting. Your recommended method will be scored by its mean coef_error over 10
seeds you never see, at the harder setting. Each run costs budget. When you are done, call submit."""


class BaselineResult(BaseModel):
    runs_used: int
    method: str | None
    deciding_condition: str | None
    reason: str | None
    turns: int
    input_tokens: int
    output_tokens: int


def _claims_text(claims: list[Claim]) -> str:
    """Give the baseline every claim field, preserving units, zero values and provenance."""
    return "\n".join(
        "- " + json.dumps(c.model_dump(), ensure_ascii=False, sort_keys=True)
        for c in claims
    )


def run_baseline(goal: Goal, claims: list[Claim], run_dir: Path) -> BaselineResult:
    adapter = get_adapter(goal.adapter)
    runner = Runner(Budget(**goal.budget.model_dump()), run_dir)
    submitted: dict = {}

    def run_experiment(
        method: str,
        noise: float,
        dt: float = 0.002,
        t_end: float = 10.0,
        noise_type: str = "gaussian",
        threshold: float = 0.1,
        seed: int = 0,
    ) -> str:
        """Simulate the Lorenz system, fit one method, and return its metrics as JSON.

        Args:
            method: One of the supported methods listed in the task.
            noise: Measurement noise as a fraction of each signal's std, e.g. 0.05.
            dt: Sampling interval in seconds.
            t_end: Length of the recorded trajectory in seconds.
            noise_type: "gaussian" or "outliers" (Gaussian plus rare sensor spikes).
            threshold: Sparsity threshold of the STLSQ regression.
            seed: Random seed for the noise.
        """
        conds = {
            "system": "lorenz",
            "noise": noise,
            "dt": dt,
            "t_end": t_end,
            "noise_type": noise_type,
            "threshold": threshold,
        }
        spec = ExperimentSpec(task=goal.task, adapter=goal.adapter, method=method, conditions=conds, seed=seed)
        try:
            result = runner.run(spec)
        except BudgetExceeded as exc:
            return json.dumps({"error": str(exc)})
        if not result.ok:
            return json.dumps({"error": result.error})
        left = goal.budget.runs - runner.runs_used
        return json.dumps({"run_id": result.id, "metrics": result.metrics, "runs_left": left})

    def submit(method: str, deciding_condition: str, reason: str) -> str:
        """Submit your final answer and stop.

        Args:
            method: The method you recommend at the harder setting.
            deciding_condition: The one condition name (as written in the papers) that causes the gap.
            reason: One or two sentences on your evidence.
        """
        submitted.update(method=method, deciding_condition=deciding_condition, reason=reason)
        return "submitted"

    prompt = (
        f"Goal: {goal.question}\n\nPapers:\n{_claims_text(claims)}\n\n"
        f"Supported methods: {', '.join(adapter.methods)}\n"
        f"Metric: coef_error (lower is better). Budget: {goal.budget.runs} runs."
    )
    turns = input_tokens = output_tokens = 0
    if llm.is_claude():
        from anthropic import beta_tool

        loop = llm.client().beta.messages.tool_runner(
            model=settings.model,
            max_tokens=16000,
            system=SYSTEM,
            output_config={"effort": "medium"},
            tools=[beta_tool(run_experiment), beta_tool(submit)],
            messages=[{"role": "user", "content": prompt}],
        )
        for message in loop:
            turns += 1
            input_tokens += message.usage.input_tokens
            output_tokens += message.usage.output_tokens
            if message.stop_reason == "refusal":
                raise llm.LLMRefusal("baseline agent declined")
            if submitted or turns >= MAX_TURNS:
                break
    else:
        for usage in llm.tool_loop(SYSTEM, prompt, [run_experiment, submit], lambda: bool(submitted), MAX_TURNS):
            turns += 1
            input_tokens += usage.get("prompt_tokens", 0)
            output_tokens += usage.get("completion_tokens", 0)

    runner.save_manifest()
    result = BaselineResult(
        runs_used=runner.runs_used,
        method=submitted.get("method"),
        deciding_condition=submitted.get("deciding_condition"),
        reason=submitted.get("reason"),
        turns=turns,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    (Path(run_dir) / "baseline.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return result


def second_opinion(inv, agent: BaselineResult) -> dict:
    """Grade the plain agent's answer against Alloy's measured verdict for the same goal and claims."""
    from alloy.experiments import compare

    verdict = inv.verdict
    alloy_cause = verdict.deciding_conditions[0] if verdict and verdict.deciding_conditions else None
    alloy_method = verdict.best_method if verdict else None
    tied = compare.too_close_to_call(inv.comparison, alloy_method) if alloy_method else []
    return {
        "agent_cause": agent.deciding_condition,
        "agent_method": agent.method,
        "agent_reason": agent.reason,
        "agent_runs": agent.runs_used,
        "alloy_cause": alloy_cause,
        "alloy_method": alloy_method or "no method question",
        "cause_agrees": agent.deciding_condition == alloy_cause,
        "method_agrees": alloy_method is None or agent.method in [alloy_method, *tied],
    }
