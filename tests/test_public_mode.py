from dataclasses import replace
from datetime import date
from pathlib import Path

from alloy.config import Settings
from alloy.ui.limits import live_runs_left, live_unlocked, record_live_run

APP = str(Path(__file__).resolve().parents[1] / "ui" / "app.py")
DAY = date(2026, 10, 22)


def test_public_mode_lowers_budget_caps(monkeypatch):
    monkeypatch.delenv("ALLOY_PUBLIC", raising=False)
    assert (Settings().max_runs, Settings().max_minutes) == (500, 60.0)
    monkeypatch.setenv("ALLOY_PUBLIC", "1")
    assert (Settings().max_runs, Settings().max_minutes) == (120, 10.0)


def test_live_passcode_is_optional_and_exact():
    open_app = Settings(live_passcode="")
    locked = Settings(live_passcode="mit-2026")
    assert live_unlocked(open_app, "")
    assert not live_unlocked(locked, "")
    assert not live_unlocked(locked, "MIT-2026")
    assert live_unlocked(locked, "mit-2026")


def test_daily_live_quota_counts_resets_and_fails_closed(tmp_path):
    s = Settings(live_runs_per_day=2, cache_dir=tmp_path)
    assert live_runs_left(s, DAY) == 2
    record_live_run(s, DAY)
    record_live_run(s, DAY)
    assert live_runs_left(s, DAY) == 0
    assert live_runs_left(s, date(2026, 10, 23)) == 2
    (tmp_path / "live_usage.json").write_text("not json")
    assert live_runs_left(s, DAY) == 0


def test_public_app_caps_budgets_and_asks_for_passcode(monkeypatch, tmp_path):
    from streamlit.testing.v1 import AppTest

    from alloy.config import settings

    public = replace(
        settings,
        public=True,
        live_passcode="mit-2026",
        valency_mcp_url="https://bond.test",
        valency_token="t",
        bond_backend="http",
        cache_dir=tmp_path,
        memory_dir=tmp_path,
    )
    monkeypatch.setattr("alloy.config.settings", public)
    app = AppTest.from_file(APP, default_timeout=30)
    app.query_params["demo"] = "1"
    app.run()
    assert not app.exception
    assert app.number_input[0].max == 120
    assert app.number_input[1].max == 10.0
    assert any(t.label == "Live passcode" for t in app.text_input)


def test_wrong_passcode_never_starts_a_live_run(monkeypatch, tmp_path):
    from unittest.mock import Mock

    from streamlit.testing.v1 import AppTest

    from alloy.config import settings

    public = replace(
        settings,
        public=True,
        live_passcode="mit-2026",
        valency_mcp_url="https://bond.test",
        valency_token="t",
        bond_backend="http",
        cache_dir=tmp_path,
        memory_dir=tmp_path,
    )
    monkeypatch.setattr("alloy.config.settings", public)
    forbidden = Mock(side_effect=AssertionError("locked live mode must not run"))
    monkeypatch.setattr("alloy.agent.loop.investigate", forbidden)
    app = AppTest.from_file(APP, default_timeout=30)
    app.query_params["demo"] = "1"
    app.run()
    app.toggle[0].set_value(True)
    app.text_input[0].input("wrong")
    app.button[0].click().run()
    assert not app.exception
    assert any("passcode" in e.value.lower() for e in app.error)
    forbidden.assert_not_called()


def test_dropdown_hides_synthetic_and_read_only_modes_unless_demo():
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(APP, default_timeout=30).run()
    assert not app.exception
    assert app.selectbox[0].options == ["Real paper pair", "Collection campaign", "Saved campaign"]
    demo = AppTest.from_file(APP, default_timeout=30)
    demo.query_params["demo"] = "1"
    demo.run()
    assert "Synthetic demonstration" in demo.selectbox[0].options
