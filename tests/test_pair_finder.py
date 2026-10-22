from pathlib import Path

import pytest

from alloy.agent import pair_finder
from alloy.agent.pair_finder import Candidate, NoPairFound, Shortlist, Stance

APP = str(Path(__file__).resolve().parents[1] / "ui" / "app.py")

PAPERS = [
    Candidate(
        id="2009.08810",
        title="Robust SINDy",
        abstract="We show the method recovers the Lorenz equations with up to 40% noise. It is fast.",
        url="https://arxiv.org/abs/2009.08810",
    ),
    Candidate(
        id="2211.16000",
        title="Spurious terms",
        abstract="Above a critical noise threshold, the  identified models contain spurious terms.",
        url="https://arxiv.org/abs/2211.16000",
    ),
    Candidate(
        id="1509.03580",
        title="Discovering governing equations",
        abstract="Sparse identification of nonlinear dynamics recovers the Lorenz system from noisy data.",
        url="https://arxiv.org/abs/1509.03580",
    ),
]
RECOVERS = Stance(
    paper="arxiv:2009.08810v2",
    stance="recovers",
    quote="recovers the Lorenz equations with up to 40%",
)
FAILS = Stance(
    paper="2211.16000",
    stance="fails",
    quote="above a critical noise threshold, the identified models",
)


def test_check_keeps_quotes_found_in_the_abstracts_and_drops_the_rest():
    shortlist = Shortlist(
        papers=[
            RECOVERS,
            FAILS,
            Stance(
                paper="2211.16000",
                stance="fails",
                quote="SINDy always fails when noise is high",
            ),
            Stance(paper="2009.08810", stance="recovers", quote="recovers"),  # too short to show a claim
            Stance(paper="9999.00001", stance="fails", quote="x" * 30),
        ]
    )
    kept, dropped = pair_finder.check(shortlist, PAPERS)
    assert [(s.paper, s.stance) for s in kept] == [
        ("2009.08810", "recovers"),
        ("2211.16000", "fails"),
    ]
    assert len(dropped) == 3
    assert any("not in Bond" in d for d in dropped)


def fake_search(results):
    return lambda query, limit=25: results


def test_find_pairs_papers_by_what_their_full_texts_state_not_the_abstract_hint(
    monkeypatch,
):
    monkeypatch.setattr(pair_finder, "search", fake_search(PAPERS))
    monkeypatch.setattr(pair_finder.llm, "parse", lambda *a, **k: Shortlist(papers=[RECOVERS, FAILS]))
    texts = {
        "2009.08810": (
            None,
            "",
            "",
        ),  # the abstract hinted recovery; the full text states no standard-SINDy result
        "2211.16000": ("fails", "STLSQ breaks down at 10% noise.", "10%"),
        "1509.03580": ("recovers", "SINDy identifies the Lorenz system.", "eta=1"),
    }
    found = pair_finder.find(
        "Does SINDy survive high noise?",
        read=texts.get,
        extracted=lambda p: p == "1509.03580",
    )
    assert found.papers == ("arxiv:1509.03580", "arxiv:2211.16000")
    assert found.stances[1].quote == "STLSQ breaks down at 10% noise."
    assert "eta=1" in found.reason and "10%" in found.reason
    assert any("2009.08810: full text states no" in line for line in found.checked)


def test_find_skips_an_unreadable_paper_and_survives_a_failed_shortlist(monkeypatch):
    def broken(*a, **k):
        raise RuntimeError("model down")

    def read(paper):
        if paper == "2009.08810":
            raise TimeoutError
        return {
            "2211.16000": ("fails", "q", "10%"),
            "1509.03580": ("recovers", "q", "1"),
        }[paper]

    monkeypatch.setattr(pair_finder, "search", fake_search(PAPERS))
    monkeypatch.setattr(pair_finder.llm, "parse", broken)
    found = pair_finder.find("anything", read=read, extracted=lambda p: True)
    assert found.papers == ("arxiv:1509.03580", "arxiv:2211.16000")
    assert any("unreadable" in line for line in found.checked)


def test_find_reports_when_no_full_text_disagrees(monkeypatch):
    monkeypatch.setattr(pair_finder, "search", fake_search(PAPERS))
    monkeypatch.setattr(pair_finder.llm, "parse", lambda *a, **k: Shortlist(papers=[RECOVERS, FAILS]))
    with pytest.raises(NoPairFound, match="none pair"):
        pair_finder.find("anything", read=lambda p: ("fails", "q", "5%"), extracted=lambda p: False)


def test_real_pair_page_names_no_paper_before_a_search():
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(APP, default_timeout=30).run()
    assert not app.exception
    assert app.selectbox[0].value == "Real paper pair"
    text = " ".join(
        [e.value for e in app.markdown] + [e.value for e in app.caption] + [t.value for t in app.text_input]
    )
    for named in ("Brunton", "Kaheman", "1509.03580", "2009.08810"):
        assert named not in text
    assert app.text_input[0].value == ""
    assert app.button[0].disabled
