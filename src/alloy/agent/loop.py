"""The six-stage investigation: search, understand, investigate, improve, verify, remember."""

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from alloy.config import settings
from alloy.contracts import Claim, ExperimentSpec, Goal, Verdict
from alloy.experiments import compare, verify
from alloy.experiments.adapters import get_adapter
from alloy.experiments.export import to_notebook
from alloy.experiments.runner import Runner
from alloy.knowledge import bond, conditions, methods
from alloy.knowledge.extract import extract_claims, load_seed
from alloy.knowledge.graph import EvidenceGraph
from alloy.memory.deadend import DeadEndMap

SEED_CLAIMS = Path(__file__).resolve().parents[3] / "data" / "seed" / "lorenz_claims.json"
ABLATION_SEEDS = [0, 1, 2]
COMPARE_SEEDS = [0, 1, 2, 3, 4]
GAP = 0.2  # minimum mean-error gap that counts as a reproduced disagreement


class Investigation(BaseModel):
    id: str
    goal: Goal
    stage: str = "search"
    claims: list[Claim] = Field(default_factory=list)
    conflict: tuple[str, str] | None = None
    condition_report: dict[str, Any] = Field(default_factory=dict)
    reproduction: dict[str, dict[str, Any]] = Field(default_factory=dict)  # claim id -> mean error, runs
    attribution: dict[str, float] = Field(default_factory=dict)  # condition -> error added by flipping it
    hard_conditions: dict[str, Any] = Field(default_factory=dict)
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    comparison: dict[str, dict[str, float]] = Field(default_factory=dict)  # method -> mean, worst
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
    claims: list[Claim] | None = None,
    run_root: Path | None = None,
    memory_dir: Path | None = None,
    referee: bool = False,
) -> Investigation:
    inv = Investigation(id=datetime.now().strftime("%Y%m%d-%H%M%S-%f"), goal=goal)
    run_dir = Path(run_root or settings.run_dir) / inv.id
    runner = Runner(goal.budget, run_dir)
    adapter = get_adapter(goal.adapter)
    deadends = DeadEndMap(Path(memory_dir or settings.memory_dir) / "deadends.jsonl")

    try:
        _run(inv, offline, claims or [], seed_claims, runner, adapter, deadends, run_dir)
        if referee and not offline and inv.verdict:
            from alloy.agent.referee import review
            inv.referee = review(inv)
    finally:
        inv.runs_used = runner.runs_used
        runner.save_manifest()
        if runner.results:
            inv.notebook = str(to_notebook(goal.question, runner.results, run_dir / "replay.ipynb"))
        (run_dir / "investigation.json").write_text(inv.model_dump_json(indent=2), encoding="utf-8")
    return inv


def _run(inv, offline, given_claims, seed_claims, runner, adapter, deadends, run_dir) -> Investigation:
    goal = inv.goal

    # 1-2. Search and map claims into the evidence graph.
    if given_claims:
        inv.claims = list(given_claims)
    elif offline:
        inv.claims = load_seed(seed_claims)
    else:
        for paper in bond.search(goal.question):
            inv.claims += extract_claims(paper, adapter.condition_keys, start=len(inv.claims) + 1)
    graph = EvidenceGraph()
    graph.add_claims(inv.claims)
    graph.save(run_dir / "graph.json")

    # 3a. Pick the first conflict an adapter can reproduce.
    inv.stage = "investigate"
    for a, b in graph.conflicts():
        report = conditions.check(a, b, adapter.condition_keys)
        if report.comparable and report.reproducible:
            break
    else:
        return _stop(inv, "no comparable, reproducible conflict found among the claims")
    inv.conflict = (a.id, b.id)
    inv.condition_report = report.__dict__

    base = ExperimentSpec(
        task=goal.task, adapter=goal.adapter, method=a.method,
        conditions=dict(report.shared), source_claims=[a.id, b.id],
    )

    def at(conds: dict) -> ExperimentSpec:
        spec = base.model_copy(deep=True)
        spec.conditions.update(conds)
        return spec

    keys = report.reproducible
    setting = {c.id: {k: c.conditions[k] for k in keys} for c in (a, b)}

    # 3b. Reproduce both claims.
    for claim in (a, b):
        err, _, runs = compare.evaluate(runner, at(setting[claim.id]), ABLATION_SEEDS)
        inv.reproduction[claim.id] = {"coef_error": err, "conditions": setting[claim.id],
                                      "run_ids": [r.id for r in runs]}
    good, bad = sorted((a, b), key=lambda c: inv.reproduction[c.id]["coef_error"])
    good_err, bad_err = (inv.reproduction[c.id]["coef_error"] for c in (good, bad))
    if bad_err - good_err < GAP:
        return _stop(inv, f"rerunning did not reproduce the gap (mean coef_error {good_err:.3f} vs {bad_err:.3f})")

    # 3c. Attribute the gap: flip one differing condition at a time from the good setting.
    if len(keys) == 1:
        key = keys[0]
        inv.attribution = {key: bad_err - good_err}
    else:
        for k in keys:
            err, _, _ = compare.evaluate(runner, at(setting[good.id] | {k: setting[bad.id][k]}), ABLATION_SEEDS)
            inv.attribution[k] = err - good_err
        key = max(inv.attribution, key=inv.attribution.get)
    inv.hard_conditions = dict(base.conditions) | setting[bad.id]
    hard = at(setting[bad.id])

    # 4. Improve: propose fixes for the weakness and compare at the hard setting.
    inv.stage = "improve"
    found = methods.propose(key, a.method, adapter.methods, offline=offline)
    inv.candidates = [c.model_dump() for c in found]
    scores: dict[str, float] = {}
    runs_by_method = {}
    for method in [a.method] + [c.method for c in found]:
        mean, worst, runs = compare.evaluate(runner, hard.model_copy(update={"method": method}), COMPARE_SEEDS)
        scores[method], runs_by_method[method] = mean, runs
        inv.comparison[method] = {"mean": mean, "worst": worst}
    best = compare.best_method(scores)

    # 6 (as we go). Remember failed runs and methods that did not beat the baseline.
    for method, runs in runs_by_method.items():
        for r in runs:
            if not r.ok:
                deadends.record(r, "run failed")
        if method != a.method and scores[method] >= scores[a.method]:
            deadends.record(runs[0], f"mean coef_error {scores[method]:.3f} did not beat "
                                     f"{a.method} ({scores[a.method]:.3f}) at the hard setting")

    if not best or best == a.method:
        return _stop(inv, f"no candidate beat {a.method} when {key}={setting[bad.id][key]}")

    # 5. Verify the winner on unseen cases.
    inv.stage = "verify"
    challenge = verify.challenge(runner, hard, best, a.method, verify.unseen_cases(key, setting[bad.id][key]))
    inv.challenge = challenge.__dict__ | {"passed": challenge.passed}

    inv.stage = "done"
    decoys = [k for k in keys if k != key]
    inv.verdict = Verdict(
        question=goal.question,
        status="resolved" if challenge.passed else "insufficient_evidence",
        explanation=(
            f"{good.id} and {bad.id} disagree because of {key} "
            f"({setting[good.id][key]} vs {setting[bad.id][key]})"
            + (f"; {', '.join(decoys)} also differ but explain little" if decoys else "")
            + f". Rerunning reproduces the gap (mean coef_error {good_err:.3f} vs {bad_err:.3f}). "
            f"At the harder setting {best} has the lowest mean error over {len(COMPARE_SEEDS)} seeds "
            f"({scores[best]:.3f} vs {scores[a.method]:.3f} for {a.method}) and won "
            f"{challenge.wins}/{len(challenge.cases)} unseen cases."
        ),
        deciding_conditions=[key],
        best_method=best,
        evidence=[a.id, b.id] + [rid for rep in inv.reproduction.values() for rid in rep["run_ids"]],
    )
    return inv
