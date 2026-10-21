"""Goal-and-budget form plus the results view. Run with: uv run streamlit run ui/app.py"""

from pathlib import Path

import pandas as pd
import streamlit as st

from alloy.agent.loop import investigate
from alloy.cli import DEFAULT_QUESTION
from alloy.config import settings
from alloy.contracts import Budget, Goal
from alloy.knowledge.extract import load_seed
from alloy.knowledge.presentation import condition_rows, evidence_label, paper_url


def show_sources(claims):
    for claim in claims:
        with st.expander(f"{claim.id} · {claim.title or claim.paper}"):
            st.caption(evidence_label(claim))
            url = paper_url(claim.paper)
            if url:
                st.link_button("Open source paper", url)
            else:
                st.text(claim.paper)
            st.text(claim.quote or "No supporting passage recorded.")
            st.caption("A source link identifies the paper; it does not verify the claim or its conditions.")

st.set_page_config(page_title="Alloy", layout="wide")
st.title("Alloy")
st.caption("Find why papers disagree, reproduce the gap, and test whether a combination beats both.")

with st.form("goal"):
    question = st.text_area("Research goal", DEFAULT_QUESTION)
    c1, c2, c3 = st.columns(3)
    runs = c1.number_input("Run budget", 10, 500, 60)
    minutes = c2.number_input("Time budget (min)", 1.0, 60.0, 5.0)
    online = c3.toggle("Use Bond + Claude (API usage)", value=False, disabled=not settings.bond_configured)
    submitted = st.form_submit_button("Investigate")

if submitted:
    st.session_state.pop("inv", None)
    with st.spinner("Investigating..."):
        try:
            st.session_state.inv = investigate(
                Goal(question=question, budget=Budget(runs=runs, minutes=minutes)),
                offline=not online,
                referee=online,
            )
        except Exception:
            st.error(
                "Investigation could not complete. "
                "Check your service configuration and installed dependencies before retrying."
            )
            st.stop()

inv = st.session_state.get("inv")
if inv is None:
    st.info("Set a goal and budget, then press Investigate. Offline mode uses the seed Lorenz claims.")
    st.warning("Offline claims are demo placeholders. No published disagreement has been verified.")
    seed_path = Path(__file__).resolve().parents[1] / "data" / "seed" / "lorenz_claims.json"
    preview = load_seed(seed_path)
    st.subheader("Starting evidence")
    show_sources(preview)
    if len(preview) >= 2:
        st.subheader("Condition comparison preview")
        st.dataframe(pd.DataFrame(condition_rows(preview[0], preview[1])), hide_index=True)
    st.stop()

if any("placeholder" in evidence_label(c).lower() for c in inv.claims):
    st.warning("Demo evidence: these claims contain placeholders. Results cannot establish a published disagreement.")
if inv.verdict:
    (st.success if inv.verdict.status == "resolved" else st.warning)(inv.verdict.explanation)
st.caption(f"{inv.runs_used} runs used · stopped at stage: {inv.stage}")

left, right = st.columns(2)
with left:
    st.subheader("Claims")
    st.dataframe(pd.DataFrame([
        {"id": c.id, "paper": c.paper, "method": c.method, "outcome": c.outcome or c.value, **c.conditions}
        for c in inv.claims
    ]), hide_index=True)
    if inv.condition_report:
        st.subheader("Condition Check")
        report = inv.condition_report
        by_id = {c.id: c for c in inv.claims}
        if report.get("a") in by_id and report.get("b") in by_id:
            st.dataframe(pd.DataFrame(condition_rows(by_id[report["a"]], by_id[report["b"]])), hide_index=True)
        if not report.get("comparable"):
            st.warning("Insufficient evidence for a controlled comparison.")
        for note in report.get("notes", []):
            st.caption(note)
    st.subheader("Source trail")
    show_sources(inv.claims)
with right:
    if inv.attribution:
        st.subheader("Which condition causes the gap")
        st.bar_chart(pd.Series(inv.attribution, name="error added"))
    st.subheader("Controlled comparison at the harder setting")
    if inv.comparison:
        table = pd.DataFrame(inv.comparison).T.round(3)
        st.bar_chart(table["mean"])
        st.dataframe(table)
    if inv.challenge:
        st.subheader("MirageLab: unseen cases")
        st.dataframe(pd.DataFrame(inv.challenge["cases"]).drop(columns="run_ids"), hide_index=True)

if inv.referee:
    st.subheader("Referee")
    for line in inv.referee:
        st.markdown(f"- {line}")

if inv.candidates:
    st.subheader("Why these methods?")
    for candidate in inv.candidates:
        st.text(f"{candidate['method']}: {candidate['rationale']}")
        source = candidate.get("source_paper")
        url = paper_url(source) if source else None
        if url:
            st.link_button(f"Source for {candidate['method']}", url)
        else:
            st.caption("No source paper recorded — candidate rationale is unverified.")

if inv.notebook:
    st.download_button("Download replay notebook", Path(inv.notebook).read_bytes(), "replay.ipynb")
st.download_button("Download investigation record", inv.model_dump_json(indent=2), "investigation.json")
