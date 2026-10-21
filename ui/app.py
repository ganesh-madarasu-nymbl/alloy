"""Evidence and saved-result views. Run with: uv run streamlit run ui/app.py"""

import json
from pathlib import Path

import networkx as nx
import pandas as pd
import streamlit as st

from alloy.agent.loop import investigate
from alloy.cli import DEFAULT_QUESTION
from alloy.config import settings
from alloy.contracts import Budget, Goal
from alloy.knowledge.extract import load_seed
from alloy.knowledge.graph import EvidenceGraph
from alloy.knowledge.presentation import condition_rows, evidence_label, paper_url
from alloy.knowledge.records import local_notebook, read_investigation
from alloy.knowledge.source_bundle import load_bundle
from alloy.memory.deadend import DeadEndMap


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
            st.caption(f"Metric: {claim.quantity} · unit: {claim.unit or 'not stated'}")
            st.caption("A source link or matching quote does not verify the measurement or its conditions.")


def show_reviewed_sources(bundle):
    st.subheader("Reviewed literature and reproduction gaps")
    st.info(bundle.description)
    for source in bundle.sources:
        with st.expander(source.title):
            st.link_button("Read primary source", str(source.source_url))
            st.caption(f"{source.evidence_type} · {source.review_status} · reviewed {source.reviewed_on}")
            st.text(source.locator)
            st.text(source.quote)
            st.write(source.outcome_summary)
            st.json(source.stated_conditions)
            for blocker in source.blockers:
                st.warning(blocker)
    st.download_button("Download reviewed evidence bundle", bundle.model_dump_json(indent=2), "evidence.json")


def show_deadends():
    st.subheader("Dead-End Map")
    st.caption("Recorded failures and losing methods apply to their recorded settings only.")
    path = settings.memory_dir / "deadends.jsonl"
    try:
        entries = DeadEndMap(path).entries() if path.exists() else []
    except (OSError, ValueError):
        st.warning("Failure history could not be read. Check the local JSONL file.")
        return
    if not entries:
        st.info("No failed or losing runs recorded in this local workspace.")
        return
    methods = sorted({str(e.get("method", "unknown")) for e in entries})
    selected = st.selectbox("Filter failure history by method", ["All methods", *methods])
    rows = [e for e in entries if selected == "All methods" or e.get("method") == selected]
    st.dataframe(pd.DataFrame(rows), hide_index=True)


st.set_page_config(page_title="Alloy", layout="wide")
st.title("Alloy")
st.caption("Investigate differences between results, test improvements, and keep an inspectable evidence trail.")
mode = st.selectbox("Evidence mode", ["Synthetic demonstration", "Reviewed literature", "Saved investigation"])
bundle = load_bundle()
eligible = bundle.summary()["eligible_cross_paper_pair"]
if mode == "Reviewed literature":
    show_reviewed_sources(bundle)
    if not eligible:
        st.warning("No eligible reviewed cross-paper pair yet. These sources cannot start a literature reproduction.")
if mode == "Saved investigation":
    st.info("Viewing a saved record does not run experiments or call a model. Its results are not reverified here.")
    uploaded = st.file_uploader("Investigation JSON", type=["json"])
    if uploaded is not None:
        try:
            st.session_state.inv = read_investigation(uploaded.getvalue())
            st.session_state.saved_record = True
        except ValueError:
            st.session_state.pop("inv", None)
            st.error("Invalid investigation record. Supply an Alloy investigation JSON smaller than 5 MB.")

with st.form("goal"):
    question = st.text_area("Research goal", DEFAULT_QUESTION)
    c1, c2, c3 = st.columns(3)
    runs = c1.number_input("Run budget", 10, 500, 60)
    minutes = c2.number_input("Time budget (min)", 1.0, 60.0, 5.0)
    online = c3.toggle(
        "Use Bond + Claude (API usage)", value=False,
        disabled=not settings.bond_configured or mode != "Synthetic demonstration",
    )
    online = online and mode == "Synthetic demonstration"
    if online:
        st.caption("Online mode searches Bond instead of using seed claims; Claude API usage applies.")
    submitted = st.form_submit_button(
        "Investigate", disabled=mode == "Saved investigation" or (mode == "Reviewed literature" and not eligible),
    )

if submitted:
    st.session_state.pop("inv", None)
    st.session_state.saved_record = False
    with st.spinner("Investigating..."):
        try:
            claims = bundle.runnable_claims() if mode == "Reviewed literature" else None
            # Never pass an empty literature list: the loop would use its synthetic fallback.
            if mode == "Reviewed literature" and not claims:
                raise ValueError("No reviewed runnable claims")
            st.session_state.inv = investigate(
                Goal(question=question, budget=Budget(runs=runs, minutes=minutes)),
                offline=not online, referee=online, claims=claims,
            )
        except Exception:
            st.error("Investigation stopped. Check dependencies, service configuration and the run budget.")
            st.info(
                "A partial investigation and run manifest may be saved under runs/. "
                "Open its JSON in Saved investigation."
            )

inv = st.session_state.get("inv")
if inv is None:
    if mode == "Synthetic demonstration":
        st.info("Set a goal and budget, then press Investigate. Offline mode uses synthetic Lorenz claims.")
        st.warning("Offline claims are demo placeholders. No published disagreement has been verified.")
        preview = load_seed(Path(__file__).resolve().parents[1] / "data/seed/lorenz_claims.json")
        st.subheader("Starting evidence")
        show_sources(preview)
        if len(preview) >= 2:
            st.subheader("Condition comparison preview")
            st.dataframe(pd.DataFrame(condition_rows(preview[0], preview[1])), hide_index=True)
    show_deadends()
    st.stop()

if st.session_state.get("saved_record"):
    st.caption("Saved result · displayed without rerunning or independently verifying its experiments")
if any("placeholder" in evidence_label(c).lower() for c in inv.claims):
    st.warning("Demo evidence: these claims contain placeholders. Results cannot establish a published disagreement.")
if inv.verdict:
    (st.success if inv.verdict.status == "resolved" else st.warning)(inv.verdict.explanation)
else:
    st.warning("Partial investigation: no final verdict was recorded.")
st.caption(f"{inv.runs_used} runs used · stopped at stage: {inv.stage}")
if inv.conflict:
    st.caption(f"Selected candidate pair: {inv.conflict[0]} / {inv.conflict[1]}")
if inv.skipped:
    with st.expander("Skipped candidate pairs"):
        for reason in inv.skipped:
            st.text(reason)

left, right = st.columns(2)
with left:
    st.subheader("Claims")
    st.dataframe(pd.DataFrame([
        {"id": c.id, "paper": c.paper, "method": c.method, "metric": c.quantity, "unit": c.unit,
         "outcome": c.outcome if c.outcome is not None else c.value, **c.conditions}
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
    if inv.reproduction:
        st.subheader("Reproduction measurements")
        st.json(inv.reproduction)
    if inv.attribution:
        st.subheader("Measured effect of changing each condition")
        st.bar_chart(pd.Series(inv.attribution, name="error added"))
        st.caption("One-at-a-time changes can miss interactions between conditions.")
    if inv.hidden_search:
        st.subheader("Unstated-setting hypotheses")
        st.warning("A matching simulation does not establish which settings the authors used.")
        st.dataframe(pd.DataFrame(inv.hidden_search).drop(columns="run_ids", errors="ignore"), hide_index=True)
    if inv.hard_conditions:
        st.subheader("Settings used for method comparison")
        st.json(inv.hard_conditions)
    st.subheader("Controlled comparison at the harder setting")
    if inv.comparison:
        table = pd.DataFrame(inv.comparison).T.round(3)
        if "mean" in table:
            st.bar_chart(table["mean"])
        st.dataframe(table)
        st.caption(
            "Mean, worst error and standard error describe the sampled seeds; unseen cases can reverse rankings."
        )
    if inv.challenge:
        st.subheader("MirageLab: unseen cases")
        st.dataframe(
            pd.DataFrame(inv.challenge.get("cases", [])).drop(columns="run_ids", errors="ignore"), hide_index=True,
        )
        st.caption(
            f"Wins: {inv.challenge.get('wins', 'not recorded')} · passed: {inv.challenge.get('passed', 'unknown')}"
        )

if inv.referee:
    st.subheader("Referee")
    for line in inv.referee:
        st.text(line)
if inv.candidates:
    st.subheader("Why these methods?")
    for candidate in inv.candidates:
        st.text(f"{candidate.get('method', 'unknown')}: {candidate.get('rationale', 'not recorded')}")
        st.caption(candidate.get("evidence_status", "unverified legacy proposal"))
        source = candidate.get("source_paper")
        url = paper_url(source) if source else None
        if url:
            st.link_button(f"Source for {candidate['method']}", url)
        if candidate.get("source_quote"):
            st.text(candidate["source_quote"])
        st.caption("Quote occurrence checks provenance only. A proposed combination still needs experimental testing.")

show_deadends()
notebook = local_notebook(inv.notebook, settings.run_dir)
if notebook:
    st.download_button("Download replay notebook", notebook, "replay.ipynb")
elif inv.notebook:
    st.caption("Replay notebook is unavailable in this workspace. Transfer the run folder separately.")
graph = EvidenceGraph()
graph.add_claims(inv.claims)
st.download_button("Download evidence graph", json.dumps(nx.node_link_data(graph.g, edges="links")), "graph.json")
st.download_button("Download investigation record", inv.model_dump_json(indent=2), "investigation.json")
