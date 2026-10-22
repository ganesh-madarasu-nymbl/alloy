"""Real paper pair: Bond finds papers, the model picks two that disagree, Alloy reproduces both and finds the cause."""

import pandas as pd
import streamlit as st

from alloy.agent import pair_finder, real_pair
from alloy.config import settings
from alloy.ui.limits import live_runs_left, live_unlocked, record_live_run


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


def show_real_pair() -> None:
    st.subheader("Real paper pair")
    st.caption(
        "Ask a question. Bond searches arXiv, the model picks two papers whose abstracts disagree, and code checks "
        "each quote against the abstract. Alloy then reads both full texts, takes every setting with its quote, "
        "reproduces both papers and tests which setting explains the disagreement. Nothing is chosen in advance."
    )
    question = st.text_input(
        "Research question",
        placeholder="e.g. Does SINDy still recover the Lorenz equations at high measurement noise?",
    )
    passcode = (
        st.text_input("Live passcode", type="password")
        if settings.live_passcode
        else ""
    )
    if st.button(
        "Find disagreeing papers", type="primary", disabled=not question.strip()
    ) and _allowed(passcode):
        st.session_state.pop("found_pair", None)
        st.session_state.pop("real_pair", None)
        with st.spinner("Searching arXiv through Bond and reading the abstracts..."):
            try:
                st.session_state.found_pair = pair_finder.find(question.strip())
            except (
                Exception
            ) as exc:  # noqa: BLE001 - show the reason instead of a stack trace
                st.error(f"No pair found: {exc}")

    found = st.session_state.get("found_pair")
    if found is None:
        st.info("Nothing has run yet. Papers appear here after Bond's search.")
        return
    st.markdown(
        f"**Bond returned {found.candidates} arXiv papers. These two disagree:**"
    )
    for s in found.stances:
        st.markdown(
            f"**{s.stance}** · [{found.titles[s.paper]}]({found.urls[s.paper]}) · arXiv {s.paper}"
        )
        st.markdown(f"> {s.quote}")
    st.caption(found.reason)

    if st.button("Run audit on this pair", type="primary") and _allowed(passcode):
        with st.spinner(
            "Reading both papers and reproducing them; a new pair takes several minutes..."
        ):
            try:
                st.session_state.real_pair = real_pair.run(
                    papers=found.papers,
                    query=found.query,
                    runs=settings.max_runs,
                    confirm=not settings.public,
                )
            except (
                Exception
            ) as exc:  # noqa: BLE001 - show the reason instead of a stack trace
                st.error(f"Audit stopped: {type(exc).__name__}: {exc}")
    report = st.session_state.get("real_pair")
    if report is None:
        return
    (st.success if report.deciding else st.warning)(report.verdict)
    scored = (
        f"scored against a hand-checked answer ({report.truth})"
        if report.truth
        else "no hand-checked answer"
    )
    st.caption(
        f"{report.runs_used} runs · Bond: {report.bond.get('status')} · {scored}"
    )
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "paper": r.paper,
                    "title": r.title,
                    "reported": f"{r.outcome} at {r.outcome_noise}",
                    "outcome from": (
                        "text" if r.outcome_source == "text" else "reviewer"
                    ),
                    "tier": r.tier.replace("_", " "),
                    "seeds recovered": r.recovered,
                }
                for r in report.results
            ]
        ),
        hide_index=True,
    )
    if report.attribution:
        st.markdown("**Which settings explain the disagreement**")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "group": g,
                        "recovering paper after flip": e["recovered_after_flip"],
                        "effect": e["effect"],
                        "failing paper after reverse flip": e[
                            "failing_paper_recovered_after_flip"
                        ],
                    }
                    for g, e in report.attribution.items()
                ]
            ),
            hide_index=True,
        )
    if report.fix:
        fix = report.fix
        st.markdown(f"**Fixing the failing setup ({fix.setup}): improve, verify, remember**")
        (st.success if fix.verified else st.info)(fix.summary)
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
    markdown = real_pair.to_markdown(report)
    with st.expander("Full audit: every setting, its source and quote"):
        st.markdown(markdown)
    st.download_button("Download real-pair audit", markdown, "real_pair.md")
