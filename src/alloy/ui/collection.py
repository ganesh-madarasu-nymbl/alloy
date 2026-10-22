"""Collection preview and saved campaign inspection; uploads are data, never instructions."""

from pathlib import Path

import pandas as pd
import streamlit as st

from alloy import config
from alloy.agent.campaign import run_campaign
from alloy.contracts import Budget, Goal
from alloy.knowledge.campaign_report import campaign_markdown
from alloy.knowledge.collection_input import read_collection
from alloy.knowledge.records import read_campaign
from alloy.knowledge.source_bundle import DEFAULT_BUNDLE

SEED_COLLECTION = Path(__file__).resolve().parents[3] / "data/seed/collection_claims.json"


def show_collection(*, saved: bool):
    if saved:
        st.info("Saved campaign inspection does not execute experiments, call a model or read uploaded file paths.")
        upload = st.file_uploader("Campaign JSON", type=["json"])
        if upload is not None:
            try:
                st.session_state.campaign = read_campaign(upload.getvalue())
            except ValueError:
                st.session_state.pop("campaign", None)
                st.error("Invalid campaign record. Supply an Alloy campaign JSON smaller than 5 MB.")
    else:
        sources = ["Reviewed evidence bundle"]
        if st.query_params.get("demo") == "1":  # the synthetic collection is listed only with ?demo=1
            sources.insert(0, "Synthetic collection")
        source = st.selectbox("Collection source", sources)
        reviewed = source == "Reviewed evidence bundle"
        if st.session_state.get("collection_source") not in (None, source):
            st.session_state.pop("campaign", None)
        st.session_state.collection_source = source
        if reviewed:
            st.caption("Only validated reviewed claims with matching implementation and protocol can run.")
        else:
            st.warning("Synthetic collection: these claims are demonstrations, not published disagreements.")
        upload = st.file_uploader("Collection JSON (optional; defaults to bundled example)", type=["json"])
        max_audits = st.number_input("Maximum audits", 1, 3, 3)
        data = upload.getvalue() if upload else (DEFAULT_BUNDLE if reviewed else SEED_COLLECTION).read_bytes()
        try:
            plan = read_collection(data, reviewed=reviewed, max_audits=max_audits)
        except (OSError, ValueError):
            st.error("Invalid collection. Limits: 20 works, 100 unique claims, 5 MB. Check evidence and source labels.")
            return None
        # A changed upload or selection must not display the previous collection's results.
        if st.session_state.get("collection_plan") not in (None, plan.model_dump_json()):
            st.session_state.pop("campaign", None)
        st.session_state.collection_plan = plan.model_dump_json()
        show_plan(plan)
        st.download_button("Download collection plan", plan.model_dump_json(indent=2), "collection-plan.json")
        with st.form("campaign_goal"):
            question = st.text_area("Collection research goal", "Audit the discrepancies in this collection")
            runs = st.number_input("Total campaign run budget", 0, config.settings.max_runs, 60)
            minutes = st.number_input("Shared time budget (min)", 0.1, config.settings.max_minutes, 5.0)
            submitted = st.form_submit_button("Run campaign", disabled=not plan.selected)
        if not plan.selected:
            st.warning("No eligible cross-paper pair. No simulation or synthetic fallback will run.")
        if submitted:
            st.session_state.pop("campaign", None)
            with st.spinner("Auditing the selected queue under one shared budget..."):
                try:
                    st.session_state.campaign = run_campaign(
                        Goal(question=question, budget=Budget(runs=runs, minutes=minutes)), plan,
                    )
                except Exception:
                    st.error("Campaign stopped. Inspect its saved campaign.json and child manifests under runs/.")
    campaign = st.session_state.get("campaign")
    if campaign is None:
        return None
    st.subheader("Campaign results")
    st.caption(f"{campaign.status} · {campaign.runs_used}/{campaign.goal.budget.runs} total runs · "
               f"{campaign.elapsed_seconds:.2f} seconds")
    st.info("Each conclusion applies to its own claim pair. No global best method is established.")
    if not campaign.accounting_complete:
        st.error("Accounting is incomplete. Displayed consumption is a known subtotal; later audits were stopped.")
    if saved:
        show_plan(campaign.plan)
    st.dataframe(pd.DataFrame([dict(pair=e.pair_id, status=e.status, cap=e.allocated_runs,
                                    consumed=e.runs_used, error=e.error) for e in campaign.audits]), hide_index=True)
    st.download_button("Download campaign record", campaign.model_dump_json(indent=2), "campaign.json")
    st.download_button("Download campaign report", campaign_markdown(campaign), "campaign.md")
    children = [e for e in campaign.audits if e.investigation is not None]
    if not children:
        st.caption("No embedded investigation is available. Deferred and failed attempts remain visible above.")
        return None
    chosen = st.selectbox("Inspect audited pair", [e.pair_id for e in children])
    st.caption("Recorded child evidence; inspection does not rerun the audit.")
    return next(e.investigation for e in children if e.pair_id == chosen)


def show_plan(plan):
    st.subheader("Collection preview")
    st.caption(f"{len(plan.claims)} claims · {len(set(plan.canonical_works.values()))} canonical works · "
               f"{len(plan.pairs)} screened pairs · {len(plan.selected)} queued audits · limits: 20 works / 100 claims")
    st.caption("Point-value differences are screening heuristics, not statistically established contradictions.")
    for warning in plan.identity_warnings:
        st.caption(warning)
    st.dataframe(pd.DataFrame([dict(pair=p.id, disposition=p.disposition, rank=p.rank, gap=p.gap,
                                   reasons="; ".join(p.reasons), ranking="; ".join(p.ranking_reasons))
                              for p in plan.pairs]), hide_index=True)
    if plan.evidence:
        st.caption(f"Reviewed source records: {len(plan.evidence.sources)}. Source-level blockers:")
        for source in plan.evidence.sources:
            with st.expander(source.title):
                st.link_button("Read source", str(source.source_url))
                st.text(source.locator)
                st.text(source.quote)
                for blocker in source.blockers:
                    st.warning(blocker)
