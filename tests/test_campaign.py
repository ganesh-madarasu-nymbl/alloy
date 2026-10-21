import json

import pytest

from alloy.agent.campaign import run_campaign
from alloy.agent.loop import Investigation
from alloy.contracts import Budget, ExperimentSpec, Goal, RunResult, Verdict
from alloy.experiments.runner import BudgetExceeded
from alloy.knowledge.campaign_report import campaign_markdown
from alloy.knowledge.collection import plan_collection
from alloy.knowledge.records import read_campaign
from test_collection import claims3


def fake_child(count=2, error=None, clock=None):
    def run(goal, *, claims, output_dir, **kwargs):
        output_dir.mkdir(parents=True)
        inv = Investigation(id=output_dir.name, goal=goal, claims=claims, conflict=tuple(c.id for c in claims))
        used = min(count, goal.budget.runs)
        results = [RunResult(id=f"r{i:03d}-fake", spec=ExperimentSpec(task=goal.task, adapter=goal.adapter,
                             method="sindy"), ok=i != 0, error="failed simulation" if i == 0 else None)
                   for i in range(used)]
        inv.runs_used = used
        inv.comparison = {"sindy": {"mean": .3, "worst": .4, "stderr": .1, "n": 2, "dropped_after": None}}
        if not error:
            inv.verdict = Verdict(question=goal.question, status="insufficient_evidence", explanation="fixture only")
        for r in results:
            (output_dir / (r.id + ".json")).write_text(r.model_dump_json())
        (output_dir / "manifest.json").write_text(json.dumps([r.model_dump() for r in results]))
        (output_dir / "investigation.json").write_text(inv.model_dump_json())
        if clock is not None:
            clock[0] += 70
        if error:
            raise error
        return inv
    return run


def goal(runs=60):
    return Goal(question="synthetic campaign", budget=Budget(runs=runs, minutes=1))


def test_shared_budget_redistributes_only_verified_unused_runs(monkeypatch, tmp_path):
    monkeypatch.setattr("alloy.agent.campaign.investigate", fake_child())
    campaign = run_campaign(goal(), plan_collection(claims3()), run_root=tmp_path)
    assert [e.allocated_runs for e in campaign.audits] == [20, 29, 56]
    assert campaign.runs_used == 6  # includes each failed simulation
    assert campaign.status == "complete"
    restored = read_campaign((tmp_path / campaign.id / "campaign.json").read_bytes())
    assert restored == campaign
    report = campaign_markdown(restored)
    assert "Synthetic demonstration" in report and "No global best" in report
    assert "Dropped after" in report and "Std error" in report
    assert all(e.investigation for e in restored.audits)


def test_budget_failure_keeps_partial_and_never_resets_cap(monkeypatch, tmp_path):
    monkeypatch.setattr("alloy.agent.campaign.investigate", fake_child(99, BudgetExceeded("fixture exhaustion")))
    campaign = run_campaign(goal(30), plan_collection(claims3()), run_root=tmp_path)
    assert [e.allocated_runs for e in campaign.audits] == [10, 10, 10]
    assert campaign.runs_used == 30
    assert all(e.status == "partial" and e.investigation.verdict is None for e in campaign.audits)
    assert campaign.status == "partial"


def test_insufficient_fair_cap_defers_without_launch(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr("alloy.agent.campaign.investigate", lambda *a, **k: calls.append(k))
    campaign = run_campaign(goal(5), plan_collection(claims3()), run_root=tmp_path)
    assert not calls
    assert all(e.status == "deferred" for e in campaign.audits)


def test_shared_deadline_not_reset_for_next_pair(monkeypatch, tmp_path):
    clock = [0]
    monkeypatch.setattr("alloy.agent.campaign.time.monotonic", lambda: clock[0])
    monkeypatch.setattr("alloy.agent.campaign.investigate", fake_child(clock=clock))
    campaign = run_campaign(goal(), plan_collection(claims3()), run_root=tmp_path)
    assert campaign.audits[0].status == "complete"
    assert all(e.status == "deferred" and "time budget" in e.error for e in campaign.audits[1:])


def test_unverifiable_manifest_stops_remaining_audits(monkeypatch, tmp_path):
    def broken(*a, **kwargs):
        raise RuntimeError("no trustworthy manifest")
    monkeypatch.setattr("alloy.agent.campaign.investigate", broken)
    campaign = run_campaign(goal(), plan_collection(claims3()), run_root=tmp_path)
    assert campaign.status == "failed" and not campaign.accounting_complete
    assert campaign.audits[0].runs_used is None
    assert all(e.status == "deferred" for e in campaign.audits[1:])
    assert "known subtotal" in campaign_markdown(campaign)


def test_interrupt_persisted_and_reraised(monkeypatch, tmp_path):
    monkeypatch.setattr("alloy.agent.campaign.investigate", fake_child(2, KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        run_campaign(goal(), plan_collection(claims3()), run_root=tmp_path)
    campaign = read_campaign(next(tmp_path.glob("*/campaign.json")).read_bytes())
    assert campaign.status == "partial" and campaign.runs_used == 2
    assert all(e.status == "deferred" for e in campaign.audits[1:])


def test_empty_and_zero_budget_never_fall_back_to_seed(monkeypatch, tmp_path):
    monkeypatch.setattr("alloy.agent.campaign.investigate", lambda *a, **k: pytest.fail("must not execute"))
    assert not run_campaign(goal(), plan_collection([]), run_root=tmp_path).audits
    assert run_campaign(goal(0), plan_collection(claims3()), run_root=tmp_path).runs_used == 0


def test_tampered_plan_and_saved_references_rejected(monkeypatch, tmp_path):
    plan = plan_collection(claims3())
    plan.pairs[0].gap = 0
    with pytest.raises(ValueError, match="screening"):
        run_campaign(goal(), plan, run_root=tmp_path)
    monkeypatch.setattr("alloy.agent.campaign.investigate", fake_child())
    campaign = run_campaign(goal(), plan_collection(claims3()), run_root=tmp_path)
    raw = campaign.model_dump()
    for key, value in [("directory", "../../private"), ("runs_used", 99), ("pair_id", "missing")]:
        changed = json.loads(json.dumps(raw))
        changed["audits"][0][key] = value
        with pytest.raises(ValueError):
            read_campaign(json.dumps(changed).encode())
    for data in (b"{}", b"no", b"x" * 5_000_001):
        with pytest.raises(ValueError):
            read_campaign(data)


@pytest.mark.parametrize("budget", [Budget(runs=-1), Budget(minutes=0), Budget(minutes=float("inf"))])
def test_invalid_budget_rejected(budget, tmp_path):
    with pytest.raises(ValueError):
        run_campaign(Goal(question="invalid", budget=budget), plan_collection([]), run_root=tmp_path)
