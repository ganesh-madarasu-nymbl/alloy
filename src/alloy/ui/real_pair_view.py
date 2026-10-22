"""Real paper pair: Bond finds papers, the model picks two that disagree, Alloy reproduces both and finds the cause."""

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from alloy.agent import pair_finder, real_pair
from alloy.config import settings
from alloy.ui.limits import live_runs_left, live_unlocked, record_live_run

FIELDS = {
    "Equations from data": None,
    "Cooling coatings": "Alloy reruns thin-film coatings with tmm from the command line (`alloy coatings`). "
    "Real-paper audits for coatings come next.",
    "Any other field": "Bond searches every field, but Alloy can only rerun a field it has an adapter for. "
    "Today that is equations from data and thin-film coatings.",
}


@dataclass(frozen=True)
class Example:
    tag: str
    question: str
    saved: str | None  # a committed audit in data/literature/examples, shown without a passcode
    status: str


EXAMPLES = (
    Example(
        "Noisy data",
        "Why does SINDy recover the Lorenz equations in some papers but fail on noisy data in others?",
        "noise-placement",
        "Checked: cause found",
    ),
    Example(
        "Weak form",
        "Is weak-form SINDy more robust to noise than standard SINDy?",
        "weak-form",
        "Checked: honest stop",
    ),
    Example(
        "Ensembles",
        "Does ensemble bagging make SINDy robust to noise and short records?",
        None,
        "Live: needs the passcode",
    ),
    Example(
        "Thresholds",
        "Does the choice of sparsity threshold explain different SINDy results?",
        None,
        "Live: needs the passcode",
    ),
)


def _allowed(passcode: str) -> bool:
    """Same rule as the other live modes: the passcode, then the daily allowance."""
    if not live_unlocked(settings, passcode):
        st.error("This needs the live passcode.")
        return False
    if settings.public and live_runs_left(settings) <= 0:
        st.error("Today's live-run allowance is used up.")
        return False
    if settings.public:
        record_live_run(settings)
    return True


def _pick(example: Example) -> None:
    st.session_state.rp_question = example.question
    for key in ("found_pair", "real_pair", "rp_saved"):
        st.session_state.pop(key, None)
    if example.saved:
        st.session_state.real_pair = real_pair.load_example(example.saved)
        st.session_state.rp_saved = example.saved


def _examples() -> None:
    st.markdown("**Or try one**")
    for col, ex in zip(st.columns(len(EXAMPLES)), EXAMPLES, strict=True):
        with col.container(border=True):
            st.caption(ex.tag.upper())
            st.markdown(ex.question)
            st.caption(ex.status)
            st.button("Try this", key=f"rp_example_{ex.tag}", on_click=_pick, args=(ex,), use_container_width=True)


def _claims(cards: list[dict]) -> None:
    """Two papers side by side: what each one says, in its own words."""
    for col, card in zip(st.columns(2), cards, strict=False):
        with col.container(border=True):
            st.caption(card["label"])
            st.markdown(f"**[{card['title']}]({card['url']})**" if card.get("url") else f"**{card['title']}**")
            show = {"recovers": st.success, "fails": st.error}.get(card["stance"], st.info)
            show(card["says"])
            if card.get("quote"):
                st.markdown(f"> {card['quote']}")


def _report_cards(report: real_pair.RealPairReport) -> list[dict]:
    cards = []
    for i, r in enumerate(report.results):
        says = (
            f"Says: standard SINDy {r.outcome} at noise {r.outcome_noise}"
            if r.outcome
            else "States no outcome for standard SINDy"
        )
        source = "from the text" if r.outcome_source == "text" else "read by a reviewer"
        cards.append(
            {
                "label": f"PAPER {'AB'[i]} · arXiv {r.paper.split(':')[-1]}",
                "title": r.title or r.paper,
                "url": r.url,
                "stance": r.outcome,
                "says": says,
                "quote": f"{r.outcome_quote} ({source})" if r.outcome_quote else None,
            }
        )
    return cards


def _headline(report: real_pair.RealPairReport) -> str:
    if report.deciding:
        return f"Both papers hold up. They disagree because of {report.deciding}."
    if any(r.outcome is None for r in report.results):
        return "Not enough evidence: one paper never states a result to reproduce."
    return "Alloy could not explain this disagreement."


def _tiles(report: real_pair.RealPairReport) -> None:
    good = next((r for r in report.results if r.outcome == "recovers"), None)
    bad = next((r for r in report.results if r.outcome == "fails"), None)
    if not (good and bad and report.deciding and good.recovered is not None and bad.recovered is not None):
        return
    flip = report.attribution[report.deciding]["recovered_after_flip"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Recovering paper's setup", f"{good.recovered:.2f}", help="Share of seeds that recover Lorenz")
    c2.metric("Failing paper's setup", f"{bad.recovered:.2f}", help="Share of seeds that recover Lorenz")
    c3.metric(
        f"Flip test: {report.deciding} moved",
        f"{flip:.2f}",
        delta=f"{flip - good.recovered:+.2f}",
        delta_color="inverse",
        help="The recovering paper's setup with only this group of settings changed",
    )


def _assumptions(report: real_pair.RealPairReport) -> None:
    if not any(r.assumptions for r in report.results):
        return
    with st.container(border=True):
        st.markdown("**What Alloy had to assume**")
        for r in report.results:
            if r.assumptions:
                st.markdown(f"*{r.title or r.paper}*")
                st.markdown("\n".join(f"- {a}" for a in r.assumptions))


def _fix(fix) -> None:
    st.markdown(f"**Fixing the failing setup ({fix.setup}): improve, verify, remember**")
    win = next((a for a in fix.arms if a.label == fix.winner), None)
    base = next((a for a in fix.arms if a.label == fix.baseline), None)
    if win and base and fix.winner != fix.baseline:
        c1, c2, c3 = st.columns(3)
        c1.metric("Best standard SINDy", f"{base.mean_error:.2f}", help=f"Coefficient error, {base.label}")
        c2.metric(
            "Winner",
            f"{win.mean_error:.2f}",
            delta=f"{win.mean_error - base.mean_error:+.2f}",
            delta_color="inverse",
            help=f"Coefficient error, {win.label}",
        )
        c3.metric("Unseen trajectories won", f"{fix.unseen_wins} / {len(fix.unseen)}")
    (st.success if fix.verified else st.info)(fix.summary)
    with st.expander(f"The race: {len(fix.arms)} method and threshold arms, {len(fix.dead_ends)} dead ends"):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "method": a.label,
                        "coefficient error": round(a.mean_error, 3),
                        "± stderr": round(a.stderr, 3),
                        "seeds": a.seeds,
                        "recovered": a.recovered,
                        "status": "winner"
                        if a.label == fix.winner
                        else "tied"
                        if a.label in fix.ties
                        else "dead end"
                        if a.dropped_after is not None
                        else "kept",
                    }
                    for a in fix.arms
                ]
            ),
            hide_index=True,
        )
        if fix.unseen:
            st.caption(f"Unseen trajectories: held-out error, {fix.winner} vs {fix.baseline}")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "start": str(list(u["start"])),
                            "noise": round(u["noise"], 3),
                            "winner": u.get(fix.winner),
                            "standard SINDy": u.get(fix.baseline),
                            "winner better": u["winner_better"],
                        }
                        for u in fix.unseen
                    ]
                ),
                hide_index=True,
            )


def _details(report: real_pair.RealPairReport) -> None:
    with st.expander("Per-paper results and every settings group tested"):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "paper": r.paper,
                        "title": r.title,
                        "reported": f"{r.outcome} at {r.outcome_noise}",
                        "outcome from": ("text" if r.outcome_source == "text" else "reviewer"),
                        "tier": r.tier.replace("_", " "),
                        "seeds recovered": r.recovered,
                    }
                    for r in report.results
                ]
            ),
            hide_index=True,
        )
        if report.attribution:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "group": g,
                            "recovering paper after flip": e["recovered_after_flip"],
                            "effect": e["effect"],
                            "failing paper after reverse flip": e["failing_paper_recovered_after_flip"],
                        }
                        for g, e in report.attribution.items()
                    ]
                ),
                hide_index=True,
            )


def show_real_pair() -> None:
    st.subheader("Real paper pair")
    st.caption(
        "Ask a question. Bond searches arXiv, the model picks two papers whose abstracts disagree, and code checks "
        "each quote against the abstract. Alloy then reads both full texts, takes every setting with its quote, "
        "reproduces both papers and tests which setting explains the disagreement. Nothing is chosen in advance."
    )
    field = st.radio("Field", list(FIELDS), horizontal=True, key="rp_field")
    if FIELDS[field]:
        st.info(FIELDS[field])
        return
    question = st.text_input(
        "Research question",
        placeholder="e.g. Does SINDy still recover the Lorenz equations at high measurement noise?",
        key="rp_question",
    )
    passcode = st.text_input("Live passcode", type="password") if settings.live_passcode else ""
    if st.button("Find disagreeing papers", type="primary", disabled=not question.strip()) and _allowed(passcode):
        for key in ("found_pair", "real_pair", "rp_saved"):
            st.session_state.pop(key, None)
        with st.spinner("Searching arXiv through Bond and reading the abstracts..."):
            try:
                st.session_state.found_pair = pair_finder.find(question.strip())
            except Exception as exc:  # noqa: BLE001 - show the reason instead of a stack trace
                st.error(f"No pair found: {exc}")
    _examples()

    found = st.session_state.get("found_pair")
    if found is not None:
        st.markdown(f"**Bond returned {found.candidates} arXiv papers. These two disagree:**")
        _claims(
            [
                {
                    "label": f"PAPER {'AB'[i]} · arXiv {s.paper}",
                    "title": found.titles[s.paper],
                    "url": found.urls[s.paper],
                    "stance": s.stance,
                    "says": f"Says: {s.stance}",
                    "quote": s.quote,
                }
                for i, s in enumerate(found.stances)
            ]
        )
        st.caption(found.reason)
        if st.button("Run audit on this pair", type="primary") and _allowed(passcode):
            with st.spinner("Reading both papers and reproducing them; a new pair takes several minutes..."):
                try:
                    st.session_state.real_pair = real_pair.run(
                        papers=found.papers,
                        query=found.query,
                        runs=settings.max_runs,
                        confirm=not settings.public,
                    )
                except Exception as exc:  # noqa: BLE001 - show the reason instead of a stack trace
                    st.error(f"Audit stopped: {type(exc).__name__}: {exc}")
    elif st.session_state.get("real_pair") is None:
        st.info("Nothing has run yet. Papers appear here after Bond's search, or pick an example above.")
        return

    report = st.session_state.get("real_pair")
    if report is None:
        return
    st.divider()
    if st.session_state.get("rp_saved"):
        st.caption("Saved audit from 22 Oct 2026, run from the committed extractions. Rerunning it needs no model key.")
        _claims(_report_cards(report))
    st.markdown(f"### {_headline(report)}")
    (st.success if report.deciding else st.warning)(report.verdict)
    scored = f"scored against a hand-checked answer ({report.truth})" if report.truth else "no hand-checked answer"
    st.caption(f"{report.runs_used} runs · Bond: {report.bond.get('status')} · {scored}")
    _tiles(report)
    _assumptions(report)
    if report.fix:
        _fix(report.fix)
    _details(report)
    markdown = real_pair.to_markdown(report)
    with st.expander("Full audit: every setting, its source and quote"):
        st.markdown(markdown)
    st.download_button("Download real-pair audit", markdown, "real_pair.md")
