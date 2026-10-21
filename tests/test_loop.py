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
