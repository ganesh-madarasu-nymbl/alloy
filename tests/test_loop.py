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


def _bench_run(name, tmp_path):
    from alloy import bench

    scenario = bench.load_scenarios([name])[0]
    return investigate(
        Goal(question=scenario.question, budget=Budget(runs=60, minutes=5)),
        offline=True,
        claims=scenario.claims,
        run_root=tmp_path / "runs",
        memory_dir=tmp_path / "memory",
    )


def test_hidden_search_finds_unstated_threshold(tmp_path):
    inv = _bench_run("hidden_threshold", tmp_path)
    assert inv.verdict.status == "likely_unstated_cause"
    assert inv.verdict.deciding_conditions == ["threshold"]


def test_distractor_conflicts_are_skipped_with_reasons(tmp_path):
    inv = _bench_run("many_papers", tmp_path)
    assert inv.conflict == ("c9", "c10")
    assert len(inv.skipped) == 3
