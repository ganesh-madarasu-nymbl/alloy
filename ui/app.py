"""Evidence and saved-result views. Run with: uv run streamlit run ui/app.py"""

import json
import sys
from pathlib import Path

import networkx as nx
import pandas as pd
import streamlit as st

# Streamlit Community Cloud installs the dependencies but may not install this package itself.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from alloy.agent.loop import investigate
from alloy.cli import DEFAULT_QUESTION
from alloy.config import settings
from alloy.contracts import Budget, Goal
from alloy.experiments.report import to_markdown
from alloy.knowledge.extract import load_seed
from alloy.knowledge.graph import EvidenceGraph
from alloy.knowledge.presentation import condition_rows, evidence_label, paper_url
from alloy.knowledge.records import local_notebook, read_investigation
from alloy.knowledge.source_bundle import load_bundle
from alloy.memory.deadend import DeadEndMap
from alloy.ui import style
from alloy.ui.agent_check import references, show_agent_check
from alloy.ui.limits import live_runs_left, live_unlocked, record_live_run

MODES = {
    "Synthetic demonstration": "<b>Synthetic demonstration.</b> Runs the full pipeline on built-in Lorenz claims "
    "in about a minute. Switch on live literature to search Bond for real papers instead.",
    "Reviewed literature": "<b>Reviewed literature.</b> Human-reviewed passages from real papers, with the gaps "
    "that still block a faithful reproduction.",
    "Saved investigation": "<b>Saved investigation.</b> Open an investigation JSON to inspect it. Nothing is rerun.",
    "Collection campaign": "<b>Collection campaign.</b> Audit several conflicting claim pairs in one budgeted run.",
    "Saved campaign": "<b>Saved campaign.</b> Inspect a finished campaign and drill into each audit.",
    "Real paper pair": "<b>Real paper pair.</b> Bond finds two real papers, arXiv supplies the full text, and "
    "Alloy reproduces both and tests which setting explains the disagreement.",
}
PUBLIC_MODES = ["Real paper pair", "Collection campaign", "Saved campaign"]


@st.cache_data(ttl=600, show_spinner=False)
def bond_reachable() -> bool:
    """Whether a real Bond request succeeds now, so the header never says connected on settings alone."""
    if not (settings.bond_backend == "http" and settings.bond_configured):
        return False
    try:
        from alloy.knowledge.http_bond import HttpBond

        HttpBond(timeout=10).open().request("tools/list")
        return True
    except Exception:  # noqa: BLE001 - any failure means Bond is not usable right now
        return False


def modes_shown(demo: bool) -> list[str]:
    """The real-paper modes by default; ?demo=1 also lists the synthetic run and the read-only views."""
    return list(MODES) if demo else PUBLIC_MODES


def show_sources(claims):
    for claim in claims:
        with st.expander(
            f"{claim.id} · {claim.title or claim.paper}", icon=":material/description:"
        ):
            st.caption(evidence_label(claim))
            url = paper_url(claim.paper)
            if url:
                st.link_button("Open source paper", url, icon=":material/open_in_new:")
            else:
                st.text(claim.paper)
            st.text(claim.quote or "No supporting passage recorded.")
            st.caption(f"Metric: {claim.quantity} · unit: {claim.unit or 'not stated'}")
            st.caption(
                "A source link or matching quote does not verify the measurement or its conditions."
            )


def show_reviewed_sources(bundle):
    st.subheader("Reviewed literature and reproduction gaps")
    st.info(bundle.description)
    for source in bundle.sources:
        with st.expander(source.title, icon=":material/menu_book:"):
            st.link_button(
                "Read primary source",
                str(source.source_url),
                icon=":material/open_in_new:",
            )
            st.caption(
                f"{source.evidence_type} · {source.review_status} · reviewed {source.reviewed_on}"
            )
            st.text(source.locator)
            st.text(source.quote)
            st.write(source.outcome_summary)
            st.json(source.stated_conditions)
            for blocker in source.blockers:
                st.warning(blocker)
    st.download_button(
        "Download reviewed evidence bundle",
        bundle.model_dump_json(indent=2),
        "evidence.json",
    )


def show_deadends():
    st.subheader("Dead-End Map")
    st.caption(
        "Recorded failures and losing methods apply to their recorded settings only."
    )
    path = settings.memory_dir / "deadends.jsonl"
    try:
        entries = DeadEndMap(path).entries() if path.exists() else []
        if not all(isinstance(entry, dict) for entry in entries):
            raise ValueError("Invalid failure history record")
    except (OSError, ValueError):
        st.warning("Failure history could not be read. Check the local JSONL file.")
        return
    if not entries:
        st.info("No failed or losing runs recorded in this local workspace.")
        return
    methods = sorted({str(e.get("method", "unknown")) for e in entries})
    selected = st.selectbox(
        "Filter failure history by method", ["All methods", *methods]
    )
    rows = [
        e for e in entries if selected == "All methods" or e.get("method") == selected
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True)


st.set_page_config(
    page_title="Alloy · why results disagree",
    page_icon=":material/hexagon:",
    layout="wide",
)
style.inject()
hero_slot = st.empty()
pick, note = st.columns([2, 3], gap="large", vertical_alignment="bottom")
mode = pick.selectbox("Evidence mode", modes_shown(st.query_params.get("demo") == "1"))
with note:
    style.mode_note(MODES[mode])
previous_mode = st.session_state.get("evidence_mode")
if previous_mode is not None and previous_mode != mode:
    if not (mode == "Saved investigation" and st.session_state.get("saved_record")):
        st.session_state.pop("inv", None)
    st.session_state.pop("campaign", None)
st.session_state.evidence_mode = mode
if mode == "Real paper pair":
    from alloy.ui.real_pair_view import show_real_pair

    with hero_slot.container():
        style.hero(None, model=settings.model, bond_live=bond_reachable())
    show_real_pair()
    st.stop()
if mode in {"Collection campaign", "Saved campaign"}:
    from alloy.ui.collection import show_collection

    child = show_collection(saved=mode == "Saved campaign")
    if child is None:
        with hero_slot.container():
            style.hero(None, model=settings.model, bond_live=bond_reachable())
        st.stop()
    st.session_state.inv = child
    st.session_state.saved_record = True
else:
    bundle = load_bundle()
    eligible = bundle.summary()["eligible_cross_paper_pair"]
    if mode == "Reviewed literature":
        show_reviewed_sources(bundle)
        if not eligible:
            st.warning(
                "No eligible reviewed cross-paper pair yet. "
                "These sources cannot start a literature reproduction."
            )
    if mode == "Saved investigation":
        st.info(
            "Viewing a saved record does not run experiments or call a model. Its results are not reverified here."
        )
        uploaded = st.file_uploader("Investigation JSON", type=["json"])
        if uploaded is not None:
            try:
                st.session_state.inv = read_investigation(uploaded.getvalue())
                st.session_state.saved_record = True
            except ValueError:
                st.session_state.pop("inv", None)
                st.error(
                    "Invalid investigation record. Supply an Alloy investigation JSON smaller than 5 MB."
                )

    with st.form("goal"):
        question = st.text_area("Research goal", DEFAULT_QUESTION, height=80)
        c1, c2, c3 = st.columns([1, 1, 1.4], vertical_alignment="center")
        runs = c1.number_input("Run budget", 10, settings.max_runs, 60)
        minutes = c2.number_input("Time budget (min)", 1.0, settings.max_minutes, 5.0)
        online = c3.toggle(
            "Live literature (Bond + model)",
            value=False,
            disabled=not settings.bond_configured or mode != "Synthetic demonstration",
            help="Search Bond for real papers and extract their claims with the configured model.",
        )
        online = online and mode == "Synthetic demonstration"
        if online:
            st.caption(
                "Live mode searches Bond instead of using seed claims; model rate limits apply."
            )
        passcode = ""
        if (
            settings.live_passcode
            and settings.bond_configured
            and mode == "Synthetic demonstration"
        ):
            passcode = st.text_input(
                "Live passcode",
                type="password",
                help="Required only for live literature.",
            )
        submitted = st.form_submit_button(
            "Investigate",
            type="primary",
            icon=":material/science:",
            disabled=mode == "Saved investigation"
            or (mode == "Reviewed literature" and not eligible),
        )

    if submitted and online and not live_unlocked(settings, passcode):
        st.error("Live literature needs the passcode. Synthetic runs need none.")
        submitted = False
    if submitted and online and live_runs_left(settings) <= 0:
        st.error(
            "Today's live-run allowance is used up. Synthetic runs are still available."
        )
        submitted = False
    if submitted:
        st.session_state.pop("inv", None)
        st.session_state.saved_record = False
        with st.spinner("Searching, reproducing and testing fixes..."):
            try:
                claims = (
                    bundle.runnable_claims() if mode == "Reviewed literature" else None
                )
                # Never pass an empty literature list: the loop would use its synthetic fallback.
                if mode == "Reviewed literature" and not claims:
                    raise ValueError("No reviewed runnable claims")
                if online:
                    record_live_run(settings)
                st.session_state.inv = investigate(
                    Goal(question=question, budget=Budget(runs=runs, minutes=minutes)),
                    offline=not online,
                    referee=online,
                    claims=claims,
                )
            except Exception:
                st.error(
                    "Investigation stopped. Check dependencies, service configuration and the run budget."
                )
                st.info(
                    "A partial investigation and run manifest may be saved under runs/. "
                    "Open its JSON in Saved investigation."
                )

inv = st.session_state.get("inv")
with hero_slot.container():
    style.hero(inv, model=settings.model, bond_live=bond_reachable())
if inv is None:
    if mode == "Synthetic demonstration":
        st.warning(
            "Offline claims are demo placeholders. No published disagreement has been verified."
        )
        preview = load_seed(
            Path(__file__).resolve().parents[1] / "data/seed/lorenz_claims.json"
        )
        evidence_tab, memory_tab = st.tabs(
            [":material/description: Starting evidence", ":material/history: Memory"]
        )
        with evidence_tab:
            if len(preview) >= 2:
                st.subheader("Condition comparison preview")
                st.dataframe(
                    pd.DataFrame(condition_rows(preview[0], preview[1])),
                    hide_index=True,
                )
            st.subheader("Starting evidence")
            show_sources(preview)
        with memory_tab:
            show_deadends()
    else:
        show_deadends()
    st.stop()

st.divider()
if st.session_state.get("saved_record"):
    st.caption(
        "Saved result · displayed without rerunning or independently verifying its experiments"
    )
if any("placeholder" in evidence_label(c).lower() for c in inv.claims):
    st.warning(
        "Demo evidence: these claims contain placeholders. Results cannot establish a published disagreement."
    )
style.verdict(inv)

best = style.best_method(inv.comparison)
cases = inv.challenge.get("cases", []) if inv.challenge else []
m1, m2, m3, m4, m5 = st.columns([1, 1, 1, 2.6, 1])
m1.metric("Runs used", inv.runs_used, border=True)
m2.metric("Claims", len(inv.claims), border=True)
m3.metric("Papers", len({c.paper for c in inv.claims}), border=True)
m4.metric("Best method", best or "—", border=True)
m5.metric(
    "Unseen wins",
    f"{inv.challenge.get('wins', 0)}/{len(cases)}" if cases else "—",
    border=True,
)
st.caption(
    f"{inv.runs_used} runs used · stopped at stage: {inv.stage}"
    + (
        f" · candidate pair: {inv.conflict[0]} / {inv.conflict[1]}"
        if inv.conflict
        else ""
    )
)

tabs = st.tabs(
    [
        ":material/description: Evidence",
        ":material/replay: Reproduce",
        ":material/trending_down: Improve & verify",
        ":material/gavel: Referee",
        ":material/history: Memory",
        ":material/download: Export",
    ]
)
with tabs[0]:
    if inv.skipped:
        with st.expander("Skipped candidate pairs"):
            for reason in inv.skipped:
                st.text(reason)
    st.subheader("Claims")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "id": c.id,
                    "paper": c.paper,
                    "method": c.method,
                    "metric": c.quantity,
                    "unit": c.unit,
                    "outcome": c.outcome if c.outcome is not None else c.value,
                    **c.conditions,
                }
                for c in inv.claims
            ]
        ),
        hide_index=True,
    )
    if inv.condition_report:
        st.subheader("Condition Check")
        report = inv.condition_report
        by_id = {c.id: c for c in inv.claims}
        if report.get("a") in by_id and report.get("b") in by_id:
            st.dataframe(
                pd.DataFrame(condition_rows(by_id[report["a"]], by_id[report["b"]])),
                hide_index=True,
            )
        if not report.get("comparable"):
            st.warning("Insufficient evidence for a controlled comparison.")
        for note_text in report.get("notes", []):
            st.caption(note_text)
    st.subheader("Source trail")
    show_sources(inv.claims)
with tabs[1]:
    if inv.reproduction:
        st.subheader("Reproduction measurements")
        st.dataframe(
            pd.DataFrame(inv.reproduction).T.drop(columns="run_ids", errors="ignore")
        )
    if inv.attribution:
        st.subheader("Measured effect of changing each condition")
        st.altair_chart(style.effect_chart(inv.attribution))
        st.caption(
            "**Figure 1.** One condition changed at a time, so interactions can be missed."
        )
    if inv.hidden_search:
        st.subheader("Unstated-setting hypotheses")
        st.warning(
            "A matching simulation does not establish which settings the authors used."
        )
        st.dataframe(
            pd.DataFrame(inv.hidden_search).drop(columns="run_ids", errors="ignore"),
            hide_index=True,
        )
    if not (inv.reproduction or inv.attribution or inv.hidden_search):
        st.info("No reproduction was run: the investigation stopped before this stage.")
with tabs[2]:
    if inv.hard_conditions:
        st.subheader("Settings used for method comparison")
        st.dataframe(pd.DataFrame([inv.hard_conditions]), hide_index=True)
    st.subheader("Controlled comparison at the harder setting")
    if inv.comparison:
        chart = style.comparison_chart(inv.comparison)
        if chart is not None:
            st.altair_chart(chart)
            st.caption(
                "**Figure 2.** Method error at the harder setting; the best method is highlighted."
            )
        st.dataframe(pd.DataFrame(inv.comparison).T.round(3))
        st.caption(
            "**Table 1.** Mean, worst and standard error over the sampled seeds; unseen cases can reverse rankings."
        )
    else:
        st.info("No method comparison was recorded.")
    if inv.challenge:
        st.subheader("MirageLab: unseen cases")
        st.dataframe(
            pd.DataFrame(inv.challenge.get("cases", [])).drop(
                columns="run_ids", errors="ignore"
            ),
            hide_index=True,
        )
        st.caption(
            f"Wins: {inv.challenge.get('wins', 'not recorded')} · passed: {inv.challenge.get('passed', 'unknown')}"
        )
    if inv.candidates:
        st.subheader("Why these methods?")
        for candidate in inv.candidates:
            with st.container(border=True):
                st.text(
                    f"{candidate.get('method', 'unknown')}: {candidate.get('rationale', 'not recorded')}"
                )
                st.caption(
                    candidate.get("evidence_status", "unverified legacy proposal")
                )
                source = candidate.get("source_paper")
                url = paper_url(source) if source else None
                if url:
                    st.link_button(
                        f"Source for {candidate.get('method', 'unknown')}", url
                    )
                if candidate.get("source_quote"):
                    st.text(candidate["source_quote"])
                st.caption(
                    "Quote occurrence checks provenance only. A proposed combination still needs experimental testing."
                )
with tabs[3]:
    if inv.referee:
        st.subheader("Referee")
        for line in inv.referee:
            st.text(line)
    else:
        st.info("The referee runs only in live literature mode.")
    second = show_agent_check(inv)
with tabs[4]:
    show_deadends()
with tabs[5]:
    notebook = (
        None
        if mode == "Saved campaign"
        else local_notebook(inv.notebook, settings.run_dir)
    )
    if notebook:
        st.download_button("Download replay notebook", notebook, "replay.ipynb")
    elif inv.notebook:
        st.caption(
            "Replay notebook is unavailable in this workspace. Transfer the run folder separately."
        )
    graph = EvidenceGraph()
    graph.add_claims(inv.claims)
    st.download_button(
        "Download evidence graph",
        json.dumps(nx.node_link_data(graph.g, edges="links")),
        "graph.json",
    )
    report = to_markdown(inv, second, references(tuple(c.paper for c in inv.claims)))
    st.download_button("Download audit report", report, "audit.md")
    st.download_button(
        "Download investigation record",
        inv.model_dump_json(indent=2),
        "investigation.json",
    )
