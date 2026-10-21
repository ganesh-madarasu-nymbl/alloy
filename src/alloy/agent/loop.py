"""The six-stage investigation: search, understand, investigate, improve, verify, remember."""

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from alloy.config import settings
from alloy.contracts import Claim, ExperimentSpec, Goal, RunResult, Verdict
from alloy.experiments import compare, verify
from alloy.experiments.adapters import get_adapter
from alloy.experiments.export import to_notebook
from alloy.experiments.runner import Runner
from alloy.knowledge import bond, conditions, methods
from alloy.knowledge.extract import extract_claims, load_seed
from alloy.knowledge.graph import EvidenceGraph
from alloy.memory.deadend import DeadEndMap

SEED_CLAIMS = Path(__file__).resolve().parents[3] / "data" / "seed" / "lorenz_claims.json"
SEEDS = [0, 1, 2]
GAP = 0.2  # minimum metric gap that counts as a reproduced disagreement


class Investigation(BaseModel):
    id: str
    goal: Goal
    stage: str = "search"
    claims: list[Claim] = Field(default_factory=list)
    conflict: tuple[str, str] | None = None
    condition_report: dict[str, Any] = Field(default_factory=dict)
    reproduction: dict[str, RunResult] = Field(default_factory=dict)
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    comparison: dict[str, dict[str, float]] = Field(default_factory=dict)
    challenge: dict[str, Any] = Field(default_factory=dict)
    verdict: Verdict | None = None
    referee: list[str] = Field(default_factory=list)
    runs_used: int = 0
    notebook: str | None = None


def _stop(inv: Investigation, why: str) -> Investigation:
    inv.verdict = Verdict(question=inv.goal.question, status="insufficient_evidence", explanation=why)
    return inv


def investigate(
    goal: Goal,
    offline: bool = True,
    seed_claims: Path = SEED_CLAIMS,
    run_root: Path | None = None,
    memory_dir: Path | None = None,
    referee: bool = False,
) -> Investigation:
    inv = Investigation(id=datetime.now().strftime("%Y%m%d-%H%M%S"), goal=goal)
    run_dir = Path(run_root or settings.run_dir) / inv.id
    runner = Runner(goal.budget, run_dir)
    adapter = get_adapter(goal.adapter)
    deadends = DeadEndMap(Path(memory_dir or settings.memory_dir) / "deadends.jsonl")

    try:
        _run(inv, offline, seed_claims, runner, adapter, deadends, run_dir)
        if referee and not offline and inv.verdict:
            from alloy.agent.referee import review
            inv.referee = review(inv)
    finally:
        inv.runs_used = runner.runs_used
        runner.save_manifest()
        if runner.results:
            inv.notebook = str(to_notebook(goal.question, runner.results, run_dir / "replay.ipynb"))
        (run_dir / "investigation.json").write_text(inv.model_dump_json(indent=2))
    return inv


def _run(inv, offline, seed_claims, runner, adapter, deadends, run_dir) -> Investigation:
    goal = inv.goal

    # 1-2. Search and map claims into the evidence graph.
    if offline:
        inv.claims = load_seed(seed_claims)
    else:
        for paper in bond.search(goal.question):
            inv.claims += extract_claims(paper, adapter.condition_keys, start=len(inv.claims) + 1)
    graph = EvidenceGraph()
    graph.add_claims(inv.claims)
    graph.save(run_dir / "graph.json")

    # 3. Investigate the first conflict that an adapter can reproduce.
    inv.stage = "investigate"
    report = None
    for a, b in graph.conflicts():
        report = conditions.check(a, b, adapter.condition_keys)
        if report.comparable and report.reproducible:
            break
    else:
        return _stop(inv, "no comparable, reproducible conflict found among the claims")
    inv.conflict = (a.id, b.id)
    inv.condition_report = report.__dict__
    key = report.reproducible[0]

    base = ExperimentSpec(
        task=goal.task, adapter=goal.adapter, method=a.method,
        conditions=dict(report.shared), source_claims=[a.id, b.id],
    )
    for claim in (a, b):
        spec = base.model_copy(deep=True)
        spec.conditions[key] = claim.conditions[key]
        inv.reproduction[claim.id] = runner.run(spec)
    errors = {cid: r.metrics.get("coef_error", float("inf")) for cid, r in inv.reproduction.items()}
    if abs(errors[a.id] - errors[b.id]) < GAP:
        return _stop(inv, f"varying {key} alone did not reproduce the gap; errors {errors}")
    hard_value = max((a, b), key=lambda c: errors[c.id]).conditions[key]

    # 4. Improve: propose fixes for the weakness and compare under one budget.
    inv.stage = "improve"
    found = methods.propose(key, a.method, adapter.methods, offline=offline)
    inv.candidates = [c.model_dump() for c in found]
    tried = [a.method] + [c.method for c in found]
    values = sorted({a.conditions[key], b.conditions[key]})
    results = compare.grid(runner, base, tried, key, values, SEEDS)
    summary = compare.summarize(results, key)
    inv.comparison = {m: {str(v): s for v, s in by.items()} for m, by in summary.items()}
    best = compare.best_method(summary, hard_value)

    # 6 (as we go). Remember failed runs and methods that lost to the baseline.
    baseline_score = summary.get(a.method, {}).get(hard_value, float("inf"))
    for r in results:
        if not r.ok:
            deadends.record(r, "run failed")
        elif r.spec.conditions.get(key) == hard_value and r.spec.method != a.method \
                and summary[r.spec.method][hard_value] >= baseline_score:
            deadends.record(r, f"did not beat {a.method} at {key}={hard_value}")

    if not best or best == a.method:
        return _stop(inv, f"no candidate beat {a.method} at {key}={hard_value}")

    # 5. Verify the winner on unseen cases.
    inv.stage = "verify"
    challenge = verify.challenge(runner, base, best, a.method)
    inv.challenge = challenge.__dict__ | {"passed": challenge.passed}

    inv.stage = "done"
    inv.verdict = Verdict(
        question=goal.question,
        status="resolved" if challenge.passed else "insufficient_evidence",
        explanation=(
            f"{a.id} and {b.id} disagree because they ran {a.method} at different {key} "
            f"({a.conditions[key]} vs {b.conditions[key]}). Rerunning reproduces the gap "
            f"(coef_error {errors[a.id]:.3f} vs {errors[b.id]:.3f}). {best} has the lowest error "
            f"at {key}={hard_value} and won {challenge.wins}/{len(challenge.cases)} unseen cases."
        ),
        deciding_conditions=[key],
        best_method=best,
        evidence=[a.id, b.id] + [r.id for r in inv.reproduction.values()],
    )
    return inv
