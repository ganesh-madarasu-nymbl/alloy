from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

from alloy.agent.baseline import BaselineResult, condition_name, second_opinion
from alloy.agent.loop import Investigation
from alloy.contracts import Goal, Verdict

APP = str(Path(__file__).resolve().parents[1] / "ui" / "app.py")


def investigation(claims=()):
    inv = Investigation(
        id="agent-check-fixture",
        goal=Goal(question="Synthetic UI fixture"),
        stage="verify",
    )
    inv.claims = list(claims)
    inv.runs_used = 12
    inv.verdict = Verdict(
        question=inv.goal.question,
        status="resolved",
        explanation="fixture",
        deciding_conditions=["noise"],
        best_method="ensemble-sindy",
    )
    inv.comparison = {
        "ensemble-sindy": {"mean": 0.10, "worst": 0.2, "stderr": 0.01},
        "weak-sindy": {"mean": 0.105, "worst": 0.2, "stderr": 0.01},
        "sindy": {"mean": 0.9, "worst": 1.0, "stderr": 0.01},
    }
    return inv


def agent(cause, method):
    return BaselineResult(
        runs_used=30,
        method=method,
        deciding_condition=cause,
        reason="fixture reason",
        turns=5,
        input_tokens=1,
        output_tokens=1,
    )


def test_second_opinion_grades_cause_and_accepts_tied_methods():
    inv = investigation()
    assert second_opinion(inv, agent("noise", "weak-sindy"))[
        "method_agrees"
    ]  # within standard error
    wrong = second_opinion(inv, agent("dt", "sindy"))
    assert not wrong["cause_agrees"] and not wrong["method_agrees"]
    assert wrong["alloy_cause"] == "noise" and wrong["agent_runs"] == 30


def _app(monkeypatch, tmp_path, inv, **overrides):
    from streamlit.testing.v1 import AppTest

    from alloy.config import settings

    monkeypatch.setattr(
        "alloy.config.settings",
        replace(
            settings,
            cache_dir=tmp_path,
            run_dir=tmp_path,
            memory_dir=tmp_path,
            **overrides,
        ),
    )
    monkeypatch.setattr("alloy.llm.configured", lambda: True)
    app = AppTest.from_file(APP, default_timeout=30)
    app.session_state["inv"] = inv
    app.session_state["saved_record"] = True
    app.run()
    app.selectbox[0].select("Saved investigation").run()
    return app


def test_agent_check_runs_the_plain_agent_and_shows_agreement(
    monkeypatch, tmp_path, seed_claims
):
    run = Mock(return_value=agent("dt", "sindy"))
    monkeypatch.setattr("alloy.ui.agent_check.run_baseline", run)
    app = _app(monkeypatch, tmp_path, investigation(seed_claims))
    next(b for b in app.button if b.label == "Ask a plain agent").click().run()
    assert not app.exception
    run.assert_called_once()
    metrics = {m.label: m for m in app.metric}
    assert metrics["Cause"].value == "dt" and metrics["Method"].value == "sindy"
    assert any("Alloy found cause noise" in c.value for c in app.caption)


def test_agent_check_needs_the_passcode_in_public_mode(
    monkeypatch, tmp_path, seed_claims
):
    run = Mock(side_effect=AssertionError("locked agent check must not run"))
    monkeypatch.setattr("alloy.ui.agent_check.run_baseline", run)
    app = _app(
        monkeypatch,
        tmp_path,
        investigation(seed_claims),
        public=True,
        live_passcode="mit-2026",
    )
    next(t for t in app.text_input if t.key == "agent_passcode").input("wrong")
    next(b for b in app.button if b.label == "Ask a plain agent").click().run()
    assert not app.exception
    assert any("passcode" in e.value for e in app.error)
    run.assert_not_called()
    assert not (tmp_path / "live_usage.json").exists()


def test_submitted_condition_is_reduced_to_its_name():
    assert condition_name("t_end (short trajectory length)") == "t_end"
    assert condition_name("  noise") == "noise"
    assert condition_name("") == ""
