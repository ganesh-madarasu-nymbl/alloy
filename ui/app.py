"""Goal-and-budget form plus the results view. Run with: uv run streamlit run ui/app.py"""

from pathlib import Path

import pandas as pd
import streamlit as st

from alloy.agent.loop import investigate
from alloy.cli import DEFAULT_QUESTION
from alloy.config import settings
from alloy.contracts import Budget, Goal

st.set_page_config(page_title="Alloy", layout="wide")
st.title("Alloy")
st.caption("Find why papers disagree, reproduce the gap, and test whether a combination beats both.")

with st.form("goal"):
    question = st.text_area("Research goal", DEFAULT_QUESTION)
    c1, c2, c3 = st.columns(3)
    runs = c1.number_input("Run budget", 10, 500, 60)
    minutes = c2.number_input("Time budget (min)", 1.0, 60.0, 5.0)
    online = c3.toggle("Use Bond + Claude", value=settings.bond_configured)
    submitted = st.form_submit_button("Investigate")

if submitted:
    with st.spinner("Investigating..."):
        st.session_state.inv = investigate(
            Goal(question=question, budget=Budget(runs=runs, minutes=minutes)),
            offline=not online,
            referee=online,
        )

inv = st.session_state.get("inv")
if inv is None:
    st.info("Set a goal and budget, then press Investigate. Offline mode uses the seed Lorenz claims.")
    st.stop()

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
        st.json({k: inv.condition_report[k] for k in ("comparable", "shared", "differing", "notes")})
with right:
    st.subheader("Controlled comparison (coefficient error)")
    if inv.comparison:
        st.line_chart(pd.DataFrame(inv.comparison))
        st.dataframe(pd.DataFrame(inv.comparison).round(3))
    if inv.challenge:
        st.subheader("MirageLab: unseen cases")
        st.dataframe(pd.DataFrame(inv.challenge["cases"]).drop(columns="run_ids"), hide_index=True)

if inv.referee:
    st.subheader("Referee")
    for line in inv.referee:
        st.markdown(f"- {line}")

if inv.notebook:
    st.download_button("Download replay notebook", Path(inv.notebook).read_bytes(), "replay.ipynb")
st.download_button("Download investigation record", inv.model_dump_json(indent=2), "investigation.json")
