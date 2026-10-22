from pathlib import Path

from alloy.agent import real_pair

APP = str(Path(__file__).resolve().parents[1] / "ui" / "app.py")


def test_committed_examples_load_and_carry_their_results():
    noise = real_pair.load_example("noise-placement")
    assert noise.deciding == "noise placement" == noise.truth
    assert noise.fix and noise.fix.verified and noise.fix.winner.startswith("smoothed-ensemble")
    weak = real_pair.load_example("weak-form")
    assert weak.deciding is None and any(r.outcome is None for r in weak.results)
    assert real_pair.load_example("missing") is None


def _app():
    from streamlit.testing.v1 import AppTest

    return AppTest.from_file(APP, default_timeout=60).run()


def _click(app, label):
    next(b for b in app.button if b.key == f"rp_example_{label}").click().run()
    assert not app.exception
    return " ".join([m.value for m in app.markdown] + [s.value for s in app.success] + [w.value for w in app.warning])


def test_checked_example_shows_claims_cause_tiles_and_fix_without_a_passcode():
    app = _app()
    text = _click(app, "Noisy data")
    assert "They disagree because of noise placement" in text
    assert "Discovering governing equations from data" in text and "Automatic Differentiation" in text
    labels = [m.label for m in app.metric]
    assert "Flip test: noise placement moved" in labels and "Unseen trajectories won" in labels
    assert "SINDy recover the Lorenz" in app.text_input[0].value


def test_weak_form_example_stops_honestly():
    text = _click(_app(), "Weak form")
    assert "Not enough evidence" in text


def test_page_states_which_papers_alloy_can_rerun():
    app = _app()
    assert not app.radio
    assert any("equations from data" in c.value for c in app.caption)
