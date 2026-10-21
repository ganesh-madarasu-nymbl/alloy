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
        by_id = {p.id: p for p in self.plan.pairs}
        claims = {c.id: c for c in self.plan.claims}
        for i, e in enumerate(self.audits):
            if e.directory != f"audits/{i + 1:02d}":
                raise ValueError("invalid audit artifact directory")
            if e.runs_used is not None and e.runs_used > e.allocated_runs:
                raise ValueError("audit exceeded its allocated cap")
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
            if e.status == "complete" and (inv is None or inv.verdict is None or e.runs_used is None):
                raise ValueError("complete audit needs a recorded verdict and verified accounting")
        return self


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
            entry.runs_used = None
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
