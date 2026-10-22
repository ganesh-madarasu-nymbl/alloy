import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from alloy.agent.campaign import run_campaign
from alloy.cli import main
from alloy.knowledge.collection import plan_collection
from alloy.knowledge.collection_input import read_collection
from test_campaign import fake_child, goal
from test_collection import claims3

APP = str(Path(__file__).resolve().parents[1] / "ui" / "app.py")


def test_collection_input_requires_seed_or_reviewed_evidence():
    claims = claims3()
    data = json.dumps([c.model_dump() for c in claims]).encode()
    assert len(read_collection(data).selected) == 3
    claims[0].source = "manual"
    with pytest.raises(ValueError, match="source='seed'"):
        read_collection(json.dumps([c.model_dump() for c in claims]).encode())
    with pytest.raises(ValueError):
        read_collection(b"x" * 5_000_001)


def test_cli_plan_only_never_executes(monkeypatch, capsys):
    run = Mock(side_effect=AssertionError("plan-only must not execute"))
    monkeypatch.setattr("alloy.agent.campaign.run_campaign", run)
    monkeypatch.setattr("sys.argv", ["alloy", "campaign", "--synthetic",
                                    "data/seed/collection_claims.json", "--plan-only"])
    main()
    assert len(json.loads(capsys.readouterr().out)["selected"]) == 3
    run.assert_not_called()


def test_collection_preview_reviewed_gaps_and_stale_state():
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(APP, default_timeout=30)

    app.query_params["demo"] = "1"

    app.run()
    app.selectbox[0].select("Collection campaign").run()
    assert not app.exception
    assert any("3 queued audits" in c.value for c in app.caption)
    app.selectbox[1].select("Reviewed evidence bundle").run()
    assert not app.exception
    assert any("No eligible cross-paper pair" in w.value for w in app.warning)
    assert app.button[0].disabled
    assert "inv" not in app.session_state


def test_saved_campaign_inspection_and_pair_selection_never_execute(monkeypatch, tmp_path):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setattr("alloy.agent.campaign.investigate", fake_child())
    campaign = run_campaign(goal(), plan_collection(claims3()), run_root=tmp_path)
    forbidden = Mock(side_effect=AssertionError("saved inspection cannot execute"))
    monkeypatch.setattr("alloy.agent.campaign.investigate", forbidden)
    monkeypatch.setattr("alloy.agent.loop.investigate", forbidden)
    monkeypatch.setattr("alloy.agent.campaign.run_campaign", forbidden)
    monkeypatch.setattr("alloy.knowledge.records.local_notebook", forbidden)
    app = AppTest.from_file(APP, default_timeout=30)
    app.query_params["demo"] = "1"
    app.run()
    app.selectbox[0].select("Saved campaign").run()
    app.session_state["campaign"] = campaign
    app.run()
    assert not app.exception
    assert len(app.get("download_button")) == 5  # campaign JSON/MD + legacy child JSON/graph/MD
    app.selectbox[1].select(campaign.audits[1].pair_id).run()
    assert not app.exception
    assert app.session_state["inv"].claims == campaign.audits[1].investigation.claims
    forbidden.assert_not_called()


def test_new_ui_launch_passes_one_total_budget(monkeypatch, tmp_path):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setattr("alloy.agent.campaign.investigate", fake_child())
    captured = []
    def launch(goal, plan):
        captured.append(goal.budget.runs)
        return run_campaign(goal, plan, run_root=tmp_path)
    monkeypatch.setattr("alloy.ui.collection.run_campaign", launch)
    app = AppTest.from_file(APP, default_timeout=30)
    app.query_params["demo"] = "1"
    app.run()
    app.selectbox[0].select("Collection campaign").run()
    app.button[0].click().run()
    assert not app.exception
    assert captured == [60]
    assert app.session_state["campaign"].runs_used == 6
