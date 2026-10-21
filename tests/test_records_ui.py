import json
from dataclasses import replace
from unittest.mock import Mock

import pytest

from alloy.agent.loop import Investigation
from alloy.contracts import Goal, Verdict
from alloy.knowledge.records import local_notebook, read_investigation


def record():
    return Investigation(id="saved-fixture", goal=Goal(question="Synthetic UI fixture"), stage="investigate")


def test_saved_record_roundtrip_and_invalid_input():
    inv = record()
    assert read_investigation(inv.model_dump_json().encode()) == inv
    for invalid in (b"{}", b"not JSON", b"x" * 5_000_001):
        with pytest.raises(ValueError):
            read_investigation(invalid)
    inv.challenge = {"cases": "bad shape"}
    with pytest.raises(ValueError, match="list"):
        read_investigation(inv.model_dump_json().encode())


def test_uploaded_notebook_paths_cannot_read_arbitrary_files(tmp_path):
    root = tmp_path / "runs"
    root.mkdir()
    notebook = root / "replay.ipynb"
    notebook.write_text("{}")
    outside = tmp_path / "private.ipynb"
    outside.write_text("private")
    assert local_notebook(str(notebook), root) == b"{}"
    assert local_notebook(str(outside), root) is None
    (root / "link.ipynb").symlink_to(outside)
    assert local_notebook(str(root / "link.ipynb"), root) is None
    assert local_notebook(str(root / "missing.ipynb"), root) is None


def test_reviewed_mode_explains_gaps_and_disables_investigation():
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file("ui/app.py").run()
    app.selectbox[0].select("Reviewed literature").run()
    assert not app.exception
    assert app.button[0].disabled
    assert any("No eligible reviewed cross-paper pair" in w.value for w in app.warning)
    assert len(app.get("download_button")) == 1


@pytest.mark.parametrize("status", [None, "resolved", "likely_unstated_cause", "insufficient_evidence"])
def test_saved_results_show_partial_verdict_hidden_search_and_exports(monkeypatch, seed_claims, status):
    from streamlit.testing.v1 import AppTest

    run = Mock(side_effect=AssertionError("Viewing must not run experiments"))
    monkeypatch.setattr("alloy.agent.loop.investigate", run)
    inv = record()
    inv.claims = seed_claims
    inv.skipped = ["c3/c4: units differ"]
    inv.hidden_search = [{"condition": "threshold", "value": 0.5, "coef_error": 0.7, "miss": 0.1}]
    inv.comparison = {"sindy": {"mean": 0.8, "worst": 1.0, "stderr": 0.1}}
    inv.challenge = {"cases": [{"noise": 0.2, "sindy": 0.8}], "wins": 0, "passed": False}
    inv.notebook = "/unavailable/replay.ipynb"
    if status:
        inv.verdict = Verdict(question=inv.goal.question, status=status, explanation="Recorded fixture verdict")
    app = AppTest.from_file("ui/app.py")
    app.session_state["inv"] = inv
    app.session_state["saved_record"] = True
    app.run()
    app.selectbox[0].select("Saved investigation").run()
    assert not app.exception
    assert any("Unstated-setting hypotheses" == s.value for s in app.subheader)
    assert any("units differ" in s.value for s in app.text)
    assert any("unavailable" in s.value for s in app.caption)
    assert len(app.get("download_button")) == 3
    run.assert_not_called()


def test_failed_run_clears_stale_verdict_and_explains_partial_record(monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setattr("alloy.agent.loop.investigate", Mock(side_effect=RuntimeError("budget exhausted")))
    app = AppTest.from_file("ui/app.py")
    app.session_state["inv"] = record()
    app.run()
    app.button[0].click().run()
    assert not app.exception
    assert any("Investigation stopped" in e.value for e in app.error)
    assert "inv" not in app.session_state


def test_dead_end_history_can_be_filtered_without_reexecution(monkeypatch, tmp_path):
    from streamlit.testing.v1 import AppTest

    from alloy.config import settings

    rows = [dict(method=m, conditions={"noise": 0.2}, metrics={}, reason="failed fixture")
            for m in ("sindy", "ensemble-sindy")]
    (tmp_path / "deadends.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    monkeypatch.setattr("alloy.config.settings", replace(settings, memory_dir=tmp_path))
    app = AppTest.from_file("ui/app.py").run()
    app.selectbox[1].select("ensemble-sindy").run()
    assert not app.exception
    assert list(app.dataframe[-1].value["method"]) == ["ensemble-sindy"]
