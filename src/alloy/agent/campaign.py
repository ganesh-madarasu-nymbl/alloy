"""Sequential pair audits sharing one budget, with durable and portable partial records."""

import json
import math
import time
import uuid
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from alloy.agent.loop import Investigation, investigate
from alloy.config import settings
from alloy.contracts import Budget, Goal, RunResult
from alloy.knowledge.collection import CollectionPlan, StrictRecord, plan_collection
from alloy.knowledge.records import read_investigation


class AuditEntry(StrictRecord):
    pair_id: str
    status: Literal["pending", "running", "complete", "partial", "failed", "deferred"] = "pending"
    allocated_runs: int = Field(default=0, ge=0)
    runs_used: int | None = Field(default=None, ge=0)
    run_ids: list[str] = Field(default_factory=list)
    directory: str
    investigation: Investigation | None = None
    error: str | None = None


class Campaign(StrictRecord):
    kind: Literal["campaign"] = "campaign"
    version: Literal[1] = 1
    id: str
    goal: Goal
    plan: CollectionPlan
    audits: list[AuditEntry]
    status: Literal["running", "complete", "partial", "failed"] = "running"
    runs_used: int = Field(default=0, ge=0)
    elapsed_seconds: float = Field(default=0, ge=0)
    accounting_complete: bool = True
    errors: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def references(self):
        _validate_goal(self.goal)
        if [e.pair_id for e in self.audits] != self.plan.selected:
            raise ValueError("audit entries must match the selected queue")
        if self.runs_used != sum(e.runs_used or 0 for e in self.audits) or self.runs_used > self.goal.budget.runs:
            raise ValueError("campaign consumption does not match audit accounting")
        if self.status != "running" and any(e.status in {"pending", "running"} for e in self.audits):
            raise ValueError("final campaign contains unfinished audit states")
        if self.accounting_complete and any(e.runs_used is None and e.status not in {"pending", "running"}
                                            for e in self.audits):
            raise ValueError("unknown audit consumption requires incomplete accounting")
        if self.status == "complete" and (not self.accounting_complete or
                                          any(e.status != "complete" for e in self.audits)):
            raise ValueError("complete campaign requires complete audits and accounting")
        by_id = {p.id: p for p in self.plan.pairs}
        claims = {c.id: c for c in self.plan.claims}
        for i, e in enumerate(self.audits):
            if e.directory != f"audits/{i + 1:02d}":
                raise ValueError("invalid audit artifact directory")
            if e.runs_used is not None and e.runs_used > e.allocated_runs:
                raise ValueError("audit exceeded its allocated cap")
            if len(set(e.run_ids)) != len(e.run_ids) or (e.runs_used is not None and len(e.run_ids) != e.runs_used):
                raise ValueError("portable run inventory disagrees with consumption")
            if e.allocated_runs > self.goal.budget.runs:
                raise ValueError("audit allocation exceeds total budget")
            inv = e.investigation
            if inv is not None:
                read_investigation(inv.model_dump_json().encode())
                expected = [claims[c] for c in by_id[e.pair_id].claims]
                if inv.claims != expected or inv.runs_used != e.runs_used or inv.goal.budget.runs != e.allocated_runs:
                    raise ValueError("embedded investigation disagrees with its pair or accounting")
                if inv.conflict is not None and tuple(inv.conflict) != by_id[e.pair_id].claims:
                    raise ValueError("embedded investigation references a different conflict")
                _validate_child(inv, e, self.goal)
            if e.status == "complete" and (inv is None or inv.verdict is None or e.runs_used is None):
                raise ValueError("complete audit needs a recorded verdict and verified accounting")
        return self


def _validate_child(inv: Investigation, entry: AuditEntry, goal: Goal):
    ids = {c.id for c in inv.claims}
    run_ids = set(entry.run_ids)
    if (inv.goal.question, inv.goal.adapter, inv.goal.task) != (goal.question, goal.adapter, goal.task):
        raise ValueError("child goal differs from campaign")
    if not math.isfinite(inv.goal.budget.minutes) or not 0 < inv.goal.budget.minutes <= goal.budget.minutes:
        raise ValueError("child time budget is invalid")
    if not set(inv.reproduction).issubset(ids):
        raise ValueError("reproduction references an unknown claim")
    if inv.verdict and not set(inv.verdict.evidence).issubset(ids | run_ids):
        raise ValueError("verdict references unknown claim or run evidence")
    for record in [*inv.reproduction.values(), *inv.hidden_search, *inv.challenge.get("cases", [])]:
        refs = record.get("run_ids", [])
        if not isinstance(refs, list) or not all(isinstance(r, str) and r in run_ids for r in refs):
            raise ValueError("measurement references an unknown run")
    for stats in inv.comparison.values():
        for key in ("n", "dropped_after"):
            value = stats.get(key)
            if value is not None and (not math.isfinite(value) or value < 0 or int(value) != value
                                      or value > (entry.runs_used or 0)):
                raise ValueError("invalid comparison sample or drop count")
        for key in ("mean", "worst", "stderr"):
            value = stats.get(key)
            if value is not None and (not math.isfinite(value) or value < 0):
                raise ValueError("comparison metrics must be finite nonnegative values or null (unavailable)")
    if inv.verdict and inv.verdict.status in {"resolved", "likely_unstated_cause"}:
        if not run_ids or set(inv.reproduction) != ids:
            raise ValueError("positive verdict requires recorded reproduction for both claims and known runs")
        reproduction_runs = set()
        for result in inv.reproduction.values():
            value = result.get("coef_error")
            if (not isinstance(value, (int, float)) or not math.isfinite(value)
                    or value < 0 or not result.get("run_ids")):
                raise ValueError("positive verdict requires finite reproduction measurements")
            if len(set(result["run_ids"])) != 3 or len(result["run_ids"]) != 3:
                raise ValueError("positive verdict requires three reproduction seeds per setting")
            reproduction_runs.update(result["run_ids"])
        differing = any(inv.claims[0].conditions.get(k) != inv.claims[1].conditions.get(k)
                        for k in inv.claims[0].conditions.keys() | inv.claims[1].conditions.keys())
        if differing and len(reproduction_runs) != 6:
            raise ValueError("different reproduction settings must use distinct runs")
        if inv.verdict.status == "resolved":
            best = inv.comparison.get(inv.verdict.best_method, {})
            if best.get("mean") is None or (best.get("n") or 0) < 2:
                raise ValueError("resolved verdict requires a sampled method")
            _validate_challenge(inv, reproduction_runs, run_ids)
        else:
            supports = [h for h in inv.hidden_search
                        if h.get("condition") in inv.verdict.deciding_conditions
                        and _finite_nonnegative(h.get("coef_error"))
                        and _finite_nonnegative(h.get("miss")) and h["miss"] <= 0.5
                        and len(h.get("run_ids", [])) == 2 and len(set(h["run_ids"])) == 2
                        and not set(h["run_ids"]) & reproduction_runs
                        and set(h["run_ids"]).issubset(inv.verdict.evidence)]
            if not supports:
                raise ValueError("hidden-cause verdict requires a finite supporting hidden-search measurement")


def _finite_nonnegative(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def _validate_challenge(inv, reproduction_runs, run_ids):
    candidate, baseline = inv.verdict.best_method, inv.claims[0].method
    challenge = inv.challenge
    cases = challenge.get("cases", [])
    if (candidate == baseline or challenge.get("candidate") != candidate or challenge.get("baseline") != baseline
            or challenge.get("passed") is not True or len(cases) != 3):
        raise ValueError("resolved verdict requires the recorded three-case unseen challenge")
    seen = set(reproduction_runs)
    for case in cases:
        refs = case.get("run_ids", [])
        if (len(refs) != 2 or len(set(refs)) != 2 or seen & set(refs)
                or not _finite_nonnegative(case.get(candidate)) or not _finite_nonnegative(case.get(baseline))
                or case[candidate] >= case[baseline] or not case.get("heldout_x0")):
            raise ValueError("resolved challenge needs distinct runs and finite winning measurements")
        seen.update(refs)
    if challenge.get("wins") != len(cases):
        raise ValueError("challenge win count disagrees with its cases")
    samples = sum(stats.get("n") or 0 for stats in inv.comparison.values())
    if len(seen) + samples > len(run_ids):
        raise ValueError("comparison and challenge sample counts exceed recorded runs")


def _validate_goal(goal: Goal):
    if goal.adapter != "pysindy" or goal.task != "equations-from-data":
        raise ValueError("campaigns currently support only the Lorenz/PySINDy investigation")
    if goal.budget.runs < 0 or not math.isfinite(goal.budget.minutes) or goal.budget.minutes <= 0:
        raise ValueError("campaign needs nonnegative runs and a positive finite time budget")


def _save(campaign: Campaign, root: Path, started: float):
    from alloy.knowledge.campaign_report import campaign_markdown

    campaign.elapsed_seconds = max(0, time.monotonic() - started)
    campaign.runs_used = sum(e.runs_used or 0 for e in campaign.audits)
    path = root / "campaign.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(campaign.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(path)
    (root / "campaign.md").write_text(campaign_markdown(campaign), encoding="utf-8")


def _reconcile(entry: AuditEntry, directory: Path, inv: Investigation | None):
    if inv is None and (directory / "investigation.json").exists():
        inv = read_investigation((directory / "investigation.json").read_bytes())
    raw = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("run manifest must be a list")
    runs = [RunResult.model_validate(r) for r in raw]
    if len({r.id for r in runs}) != len(runs) or len(runs) > entry.allocated_runs:
        raise ValueError("manifest contains duplicate runs or exceeds the child cap")
    files = sorted(directory.glob("r*.json"))
    file_runs = [RunResult.model_validate_json(p.read_bytes()) for p in files]
    if sorted(r.model_dump_json() for r in file_runs) != sorted(r.model_dump_json() for r in runs):
        raise ValueError("manifest and individual run records disagree")
    if inv is not None and inv.runs_used != len(runs):
        raise ValueError("investigation and manifest consumption disagree")
    entry.runs_used = len(runs)
    entry.run_ids = [r.id for r in runs]
    entry.investigation = inv


def run_campaign(goal: Goal, plan: CollectionPlan, *, run_root: Path | None = None) -> Campaign:
    _validate_goal(goal)
    expected = plan_collection(plan.claims, evidence=plan.evidence, max_audits=plan.max_audits)
    if plan != expected:
        raise ValueError("collection plan does not match deterministic evidence screening")
    root = Path(run_root or settings.run_dir) / ("campaign-" + uuid.uuid4().hex)
    root.mkdir(parents=True)
    started = time.monotonic()
    deadline = started + 60 * goal.budget.minutes
    campaign = Campaign(id=root.name, goal=goal, plan=plan,
                        audits=[AuditEntry(pair_id=id, directory=f"audits/{i + 1:02d}")
                                for i, id in enumerate(plan.selected)])
    _save(campaign, root, started)
    pairs = {p.id: p for p in plan.pairs}
    claims = {c.id: c for c in plan.claims}
    stop_reason = None
    for i, entry in enumerate(campaign.audits):
        remaining_seconds = deadline - time.monotonic()
        cap = (goal.budget.runs - campaign.runs_used) // (len(campaign.audits) - i)
        pair = pairs[entry.pair_id]
        minimum = 6 if pair.condition_report["differing"] else 3
        reason = stop_reason or ("shared time budget expired" if remaining_seconds <= 0 else None)
        reason = reason or (f"fair allocation {cap} cannot fund minimum reproduction cost {minimum}" if cap < minimum
                            else None)
        if reason:
            entry.status, entry.runs_used, entry.error = "deferred", 0, reason
            _save(campaign, root, started)
            continue
        entry.allocated_runs, entry.status = cap, "running"
        _save(campaign, root, started)
        remaining_seconds = deadline - time.monotonic()
        if remaining_seconds <= 0:
            entry.status, entry.runs_used, entry.allocated_runs = "deferred", 0, 0
            entry.error = "shared time budget expired before child launch"
            _save(campaign, root, started)
            continue
        child_goal = goal.model_copy(deep=True, update={"budget": Budget(runs=cap, minutes=remaining_seconds / 60)})
        inv, interruption = None, None
        try:
            inv = investigate(child_goal, offline=True, referee=False, claims=[claims[c] for c in pair.claims],
                              output_dir=root / entry.directory, memory_dir=root / "memory")
        except (KeyboardInterrupt, SystemExit) as exc:
            interruption = exc
            entry.error = f"interrupted: {type(exc).__name__}"
        except Exception as exc:
            entry.error = f"{type(exc).__name__}: {exc}"
        try:
            _reconcile(entry, root / entry.directory, inv)
            entry.status = "complete" if entry.investigation and entry.investigation.verdict else (
                "partial" if entry.investigation else "failed")
            # Validate child claims/references and counts before any redistribution.
            Campaign.model_validate(campaign.model_dump() | {
                "runs_used": sum(e.runs_used or 0 for e in campaign.audits),
            })
        except (OSError, ValueError, TypeError) as exc:
            entry.status = "failed"
            entry.investigation = None
            campaign.accounting_complete = False
            stop_reason = f"accounting failure; no further audits launched: {exc}"
            campaign.errors.append(stop_reason)
        _save(campaign, root, started)
        if interruption is not None:
            campaign.status = "partial" if campaign.accounting_complete else "failed"
            for later in campaign.audits[i + 1:]:
                later.status, later.runs_used, later.error = "deferred", 0, "campaign interrupted; no automatic resume"
            _save(campaign, root, started)
            raise interruption
    campaign.status = ("failed" if not campaign.accounting_complete else
                       "complete" if all(e.status == "complete" for e in campaign.audits) else "partial")
    _save(campaign, root, started)
    return campaign
