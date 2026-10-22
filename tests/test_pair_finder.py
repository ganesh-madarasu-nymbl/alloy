from pathlib import Path

import pytest

from alloy.agent import pair_finder
from alloy.agent.pair_finder import Candidate, NoPairFound, PairChoice, Stance

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
]


def choice(
    fails_quote="above a critical noise threshold, the identified models contain spurious terms",
):
    return PairChoice(
        stances=[
            Stance(paper="2211.16000", stance="fails", quote=fails_quote),
            Stance(
                paper="arxiv:2009.08810v2",
                stance="recovers",
                quote="recovers the Lorenz equations with up to 40%",
            ),
        ],
        reason="They disagree about high noise.",
    )


def test_check_accepts_quotes_found_in_the_abstracts_and_puts_the_recovering_paper_first():
    stances = pair_finder.check(choice(), PAPERS)
    assert [(s.paper, s.stance) for s in stances] == [
        ("2009.08810", "recovers"),
        ("2211.16000", "fails"),
    ]


@pytest.mark.parametrize(
    "bad",
    [
        choice(
            fails_quote="SINDy always fails when noise is high in every case"
        ),  # not in the abstract
        choice(fails_quote="spurious terms"),  # too short to show a claim
        PairChoice(
            stances=[Stance(paper="9999.00001", stance="fails", quote="x" * 30)],
            reason="",
        ),
        PairChoice(
            stances=[
                Stance(
                    paper="2009.08810",
                    stance="recovers",
                    quote="recovers the Lorenz equations with up to 40%",
                ),
                Stance(
                    paper="2211.16000",
                    stance="recovers",
                    quote="the identified models contain spurious terms",
                ),
            ],
            reason="",
        ),
    ],
)
def test_check_rejects_made_up_quotes_unknown_papers_and_one_sided_pairs(bad):
    with pytest.raises(NoPairFound):
        pair_finder.check(bad, PAPERS)


def test_find_retries_once_after_a_rejected_quote(monkeypatch):
    replies = iter(
        [
            choice(fails_quote="SINDy always fails when noise is high in every case"),
            choice(),
        ]
    )
    prompts = []

    def fake_parse(prompt, schema, system=None, effort="medium"):
        prompts.append(prompt)
        return next(replies)

    monkeypatch.setattr(pair_finder, "search", lambda query, limit=20: PAPERS)
    monkeypatch.setattr(pair_finder.llm, "parse", fake_parse)
    found = pair_finder.find("Does SINDy survive high noise?")
    assert found.papers == ("arxiv:2009.08810", "arxiv:2211.16000")
    assert "rejected" in prompts[1]


def test_find_reports_when_no_pair_disagrees(monkeypatch):
    monkeypatch.setattr(pair_finder, "search", lambda query, limit=20: PAPERS)
    monkeypatch.setattr(
        pair_finder.llm, "parse", lambda *a, **k: PairChoice(stances=[], reason="")
    )
    with pytest.raises(NoPairFound, match="disagree"):
        pair_finder.find("anything")


def test_real_pair_page_names_no_paper_before_a_search():
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(APP, default_timeout=30).run()
    assert not app.exception
    assert app.selectbox[0].value == "Real paper pair"
    text = " ".join(
        [e.value for e in app.markdown]
        + [e.value for e in app.caption]
        + [t.value for t in app.text_input]
    )
    for named in ("Brunton", "Kaheman", "1509.03580", "2009.08810"):
        assert named not in text
    assert app.text_input[0].value == ""
    assert app.button[0].disabled
