"""The six-stage investigation: search, understand, investigate, improve, verify, remember."""

import uuid
from datetime import datetime
from math import isfinite
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from alloy.config import settings
from alloy.contracts import Claim, ExperimentSpec, Goal, Verdict
from alloy.experiments import compare, verify
from alloy.experiments import report as audit_report
from alloy.experiments.adapters import get_adapter
from alloy.experiments.export import to_notebook
from alloy.experiments.runner import Runner
from alloy.knowledge import bond, conditions, methods
from alloy.knowledge.extract import extract_claims, load_seed
from alloy.knowledge.graph import EvidenceGraph
from alloy.memory.deadend import DeadEndMap

SEED_CLAIMS = Path(__file__).resolve().parents[3] / "data" / "seed" / "lorenz_claims.json"
ABLATION_SEEDS = [0, 1, 2]
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
    hidden_search: list[dict[str, Any]] = Field(default_factory=list)  # unstated settings tried
    skipped: list[str] = Field(default_factory=list)  # conflicts set aside, with the reason
    hard_conditions: dict[str, Any] = Field(default_factory=dict)
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    comparison: dict[str, dict[str, float | None]] = Field(default_factory=dict)  # adaptive counts/drop markers
    challenge: dict[str, Any] = Field(default_factory=dict)
    verdict: Verdict | None = None
    referee: list[str] = Field(default_factory=list)
    runs_used: int = 0
    notebook: str | None = None


def _stop(inv: Investigation, why: str) -> Investigation:
    inv.verdict = Verdict(question=inv.goal.question, status="insufficient_evidence", explanation=why)
    return inv


HIDDEN_SEEDS = [0, 1]
MATCH_TOL = 0.5  # relative miss allowed when an unstated setting reproduces the reported value


def _hidden_search(inv, runner, at, good_setting, good, bad, adapter) -> Investigation:
    """The stated conditions do not explain the gap. Try settings neither paper reports and find
    the one that reproduces the worse paper's number."""
    stated = set(good.conditions) | set(bad.conditions)
    for key in [k for k in adapter.sweeps if k not in stated]:
        for value in adapter.sweeps[key]:
            err, _, runs = compare.evaluate(runner, at(good_setting | {key: value}), HIDDEN_SEEDS)
            inv.hidden_search.append(
                {
                    "condition": key,
                    "value": value,
                    "coef_error": err,
                    "miss": abs(err - bad.value) / max(abs(bad.value), 1e-9),
                    "run_ids": [r.id for r in runs],
                }
            )
    if not inv.hidden_search:
        return _stop(inv, "the stated conditions match and the adapter has no unstated settings to try")
    valid = [h for h in inv.hidden_search if isfinite(h["coef_error"]) and isfinite(h["miss"])]
    if not valid:
        return _stop(inv, "no finite successful simulation supports an unstated-setting hypothesis")
    hit = min(valid, key=lambda h: h["miss"])
    if hit["miss"] > MATCH_TOL:
        return _stop(inv, f"no single unstated setting reproduces {bad.id}'s reported {bad.value}")

    inv.stage = "done"
    inv.verdict = Verdict(
        question=inv.goal.question,
        status="likely_unstated_cause",
        explanation=(
            f"{good.id} and {bad.id} state the same conditions but report {good.value} vs {bad.value}. "
            f"Their stated settings do not reproduce the gap. Setting {hit['condition']}={hit['value']}, "
            f"which neither paper reports, reproduces {bad.id}'s number (mean coef_error {hit['coef_error']:.3f}). "
            f"Ask {bad.paper}'s authors which {hit['condition']} they used before relying on either result."
        ),
        deciding_conditions=[hit["condition"]],
        evidence=[good.id, bad.id] + hit["run_ids"],
    )
    return inv


def investigate(
    goal: Goal,
    offline: bool = True,
    seed_claims: Path = SEED_CLAIMS,
    claims: list[Claim] | None = None,
    run_root: Path | None = None,
    memory_dir: Path | None = None,
    referee: bool = False,
    *,
    output_dir: Path | None = None,
) -> Investigation:
    # A random suffix keeps runs apart when two start in the same clock tick (Windows, shared hosting).
    inv = Investigation(
        id=f"{datetime.now():%Y%m%d-%H%M%S-%f}-{uuid.uuid4().hex[:6]}", goal=goal, claims=list(claims or [])
    )
    run_dir = Path(output_dir) if output_dir is not None else Path(run_root or settings.run_dir) / inv.id
    runner = Runner(goal.budget, run_dir)
    deadends = DeadEndMap(Path(memory_dir or settings.memory_dir) / "deadends.jsonl")

    try:
        adapter = get_adapter(goal.adapter)
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
        audit_report.write(inv, run_dir)
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
            # A paper whose claims fail the evidence gates is set aside, not allowed to end the search.
            try:
                inv.claims += extract_claims(paper, adapter.condition_keys, start=len(inv.claims) + 1)
            except ValueError as e:
                inv.skipped.append(f"{paper.id}: claims rejected ({e})")
    graph = EvidenceGraph()
    graph.add_claims(inv.claims)
    graph.save(run_dir / "graph.json")

    # 3a. Pick the first comparable conflict the adapter can run. Log why the others were skipped.
    inv.stage = "investigate"
    for a, b in graph.conflicts():
        report = conditions.check(a, b, adapter.condition_keys)
        unrunnable = (report.shared | {k: v[0] for k, v in report.differing.items()}).keys() - set(
            adapter.condition_keys
        )
        if issue := conditions.measurement_issue(a) or conditions.measurement_issue(b):
            inv.skipped.append(f"{a.id}/{b.id}: {issue}")
        elif a.method not in adapter.methods:
            inv.skipped.append(f"{a.id}/{b.id}: method {a.method} is not supported by {adapter.name}")
        elif not report.comparable:
            inv.skipped.append(f"{a.id}/{b.id}: not comparable ({'; '.join(report.notes)})")
        elif report.shared.get("system", "lorenz") != "lorenz" or unrunnable:
            inv.skipped.append(f"{a.id}/{b.id}: conditions the adapter cannot run")
        else:
            break
    else:
        return _stop(inv, "no comparable, reproducible conflict found among the claims")
    inv.conflict = (a.id, b.id)
    inv.condition_report = report.__dict__

    base = ExperimentSpec(
        task=goal.task,
        adapter=goal.adapter,
        method=a.method,
        conditions=dict(report.shared),
        source_claims=[a.id, b.id],
    )

    def at(conds: dict) -> ExperimentSpec:
        spec = base.model_copy(deep=True)
        spec.conditions.update(conds)
        return spec

    keys = report.reproducible
    setting = {c.id: {k: c.conditions[k] for k in keys} for c in (a, b)}

    # 3b. Reproduce both claims at their stated settings (one run set when the settings match).
    for claim in (a, b):
        if claim is b and setting[a.id] == setting[b.id]:
            inv.reproduction[b.id] = dict(inv.reproduction[a.id])
            continue
        err, _, runs = compare.evaluate(runner, at(setting[claim.id]), ABLATION_SEEDS)
        inv.reproduction[claim.id] = {
            "coef_error": err,
            "conditions": setting[claim.id],
            "run_ids": [r.id for r in runs],
        }
    numeric = a.value is not None and b.value is not None
    rank = (lambda c: c.value) if numeric else (lambda c: inv.reproduction[c.id]["coef_error"])
    good, bad = sorted((a, b), key=rank)
    good_err, bad_err = (inv.reproduction[c.id]["coef_error"] for c in (good, bad))
    if bad_err - good_err < GAP:
        if numeric:
            return _hidden_search(inv, runner, at, setting[good.id], good, bad, adapter)
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
    tried = [a.method] + [c.method for c in found]
    specs = {m: hard.model_copy(deep=True, update={"method": m}) for m in tried}
    inv.comparison, runs_by_method, best = compare.adaptive(runner, specs)
    if not best:
        return _stop(inv, "comparison has no finite, sufficiently sampled method; no winner established")
    scores = {m: c["mean"] for m, c in inv.comparison.items()}
    close = [m for m, c in inv.comparison.items() if m != best and c["dropped_after"] is None]

    # 6 (as we go). Remember failed runs and methods that did not beat the baseline.
    for method, runs in runs_by_method.items():
        for r in runs:
            if not r.ok:
                deadends.record(r, "run failed")
        if method != a.method and scores[method] >= scores[a.method]:
            deadends.record(
                runs[0],
                f"mean coef_error {scores[method]:.3f} did not beat "
                f"{a.method} ({scores[a.method]:.3f}) at the hard setting",
            )

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
            f"At the harder setting {best} has the lowest mean error over {inv.comparison[best]['n']} seeds "
            f"({scores[best]:.3f} vs {scores[a.method]:.3f} for {a.method}) and won "
            f"{challenge.wins}/{len(challenge.cases)} unseen cases."
            + (f" {', '.join(close)} is within seed noise of {best}; treat them as tied." if close else "")
        ),
        deciding_conditions=[key],
        best_method=best,
        evidence=[a.id, b.id] + [rid for rep in inv.reproduction.values() for rid in rep["run_ids"]],
    )
    return inv
