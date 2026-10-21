from alloy.agent.loop import investigate
from alloy.contracts import Budget, Goal


def test_offline_investigation_end_to_end(tmp_path):
    inv = investigate(
        Goal(question="test", budget=Budget(runs=60, minutes=5)),
        offline=True,
        run_root=tmp_path / "runs",
        memory_dir=tmp_path / "memory",
    )
    assert inv.stage == "done"
    assert inv.conflict == ("c1", "c2")
    assert inv.verdict.deciding_conditions == ["noise"]
    assert inv.verdict.best_method != "sindy"
    assert (tmp_path / "runs" / inv.id / "replay.ipynb").exists()


def test_attribution_finds_the_real_cause_among_decoys(tmp_path):
    from alloy import bench

    scenario = bench.load_scenarios(["short_record"])[0]
    inv = investigate(
        Goal(question=scenario.question, budget=Budget(runs=60, minutes=5)),
        offline=True,
        claims=scenario.claims,
        run_root=tmp_path / "runs",
        memory_dir=tmp_path / "memory",
    )
    assert set(inv.attribution) == {"noise", "dt", "t_end"}
    assert inv.verdict.deciding_conditions == ["t_end"]
