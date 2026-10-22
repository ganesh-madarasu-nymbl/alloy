"""Real paper pair: Bond finds the papers, arXiv supplies the text, Alloy reproduces both and finds the cause."""

import json

import pandas as pd
import streamlit as st

from alloy.agent import real_pair
from alloy.config import settings


def _latest():
    reports = sorted(settings.run_dir.glob("real-pair-*/real_pair.json"), key=lambda p: p.stat().st_mtime)
    return real_pair.RealPairReport(**json.loads(reports[-1].read_text(encoding="utf-8"))) if reports else None


def show_real_pair() -> None:
    st.subheader("Real paper pair")
    st.caption(
        "Settings come from each paper's full text (arXiv HTML) with a quote for every value. Gaps are filled by rule "
        "and labelled; outcomes read from figures are marked as reviewer-read. Brunton vs Kaheman has a hand-checked "
        "answer, so it is the one scored pair."
    )
    c1, c2, c3 = st.columns([2, 2, 1], vertical_alignment="bottom")
    a = c1.text_input("Paper A (arXiv id)", real_pair.DEFAULT_PAIR[0])
    b = c2.text_input("Paper B (arXiv id)", real_pair.DEFAULT_PAIR[1])
    run = c3.button("Run audit", type="primary")
    if run:
        with st.spinner("Reproducing both papers..."):
            try:
                st.session_state.real_pair = real_pair.run(
                    papers=(a.strip(), b.strip()), runs=settings.max_runs, confirm=not settings.public
                )
            except Exception as exc:  # noqa: BLE001 - show the reason instead of a stack trace
                st.error(f"Audit stopped: {type(exc).__name__}: {exc}")
    report = st.session_state.get("real_pair") or _latest()
    if report is None:
        st.info("Press Run audit. With the committed extractions this needs no model key.")
        return
    (st.success if report.deciding else st.warning)(report.verdict)
    st.caption(f"{report.runs_used} runs · Bond: {report.bond.get('status')}")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "paper": r.paper,
                    "title": r.title,
                    "reported": f"{r.outcome} at {r.outcome_noise}",
                    "outcome from": "text" if r.outcome_source == "text" else "reviewer",
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
                        "failing paper after reverse flip": e["failing_paper_recovered_after_flip"],
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
