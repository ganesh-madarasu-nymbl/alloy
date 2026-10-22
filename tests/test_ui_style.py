from types import SimpleNamespace

from alloy.ui import style


def test_stage_states_marks_stop_point():
    assert style.stage_states(None) == ["idle"] * 6
    assert style.stage_states(SimpleNamespace(stage="done")) == ["done"] * 6
    assert style.stage_states(SimpleNamespace(stage="improve")) == [
        "done",
        "done",
        "done",
        "stop",
        "idle",
        "idle",
    ]


def test_best_method_picks_lowest_mean_and_skips_bad_rows():
    comparison = {
        "sindy": {"mean": 1.3},
        "smoothed": {"mean": 0.57},
        "broken": {"mean": None},
        "note": "x",
    }
    assert style.best_method(comparison) == "smoothed"
    assert style.best_method({}) is None
    assert style.comparison_chart({}) is None
