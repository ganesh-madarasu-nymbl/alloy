"""Alloy audits the agent: a plain tool-using agent answers the same goal, Alloy's measurements grade it."""

import streamlit as st

from alloy import config, llm
from alloy.agent.baseline import run_baseline, second_opinion
from alloy.knowledge.citations import bibtex
from alloy.ui.limits import live_runs_left, live_unlocked, record_live_run


@st.cache_data(ttl=3600, show_spinner=False)
def references(papers: tuple[str, ...]) -> dict[str, str]:
    """BibTeX for the report, fetched from Bond once per paper set when the deployment has a Bond login."""
    return bibtex(list(papers), fetch=config.settings.bond_configured)


def show_agent_check(inv) -> dict | None:
    """Render the second opinion for `inv` and return it once it exists."""
    settings = config.settings
    opinions = st.session_state.setdefault("second_opinions", {})
    st.subheader("Second opinion on a plain agent")
    st.caption(
        "A plain agent gets the same claims, simulator and run budget, but none of Alloy's checks. "
        "Alloy's measured verdict grades its answer."
    )
    if inv.id not in opinions:
        if not inv.claims:
            st.info("This investigation has no claims to give the agent.")
            return None
        if not llm.configured():
            st.info("The agent needs a model key, and this deployment has none.")
            return None
        passcode = ""
        if settings.live_passcode:
            passcode = st.text_input("Live passcode", type="password", key="agent_passcode",
                                     help="The agent uses the shared model key.")
        if st.button("Ask a plain agent", icon=":material/smart_toy:"):
            if not live_unlocked(settings, passcode):
                st.error("The agent check needs the live passcode.")
            elif live_runs_left(settings) <= 0:
                st.error("Today's live-run allowance is used up.")
            else:
                record_live_run(settings)
                with st.spinner("The agent is running its own experiments..."):
                    try:
                        agent = run_baseline(inv.goal, inv.claims, settings.run_dir / inv.id / "agent")
                        opinions[inv.id] = second_opinion(inv, agent)
                    except Exception as exc:  # noqa: BLE001 - show the reason instead of a stack trace
                        st.error(f"Agent check stopped: {type(exc).__name__}: {exc}")
    so = opinions.get(inv.id)
    if so is None:
        return None

    def mark(agrees):
        return "agrees" if agrees else "disagrees"

    c1, c2, c3 = st.columns(3)
    c1.metric("Cause", so["agent_cause"] or "none", mark(so["cause_agrees"]),
              delta_color="normal" if so["cause_agrees"] else "inverse", border=True)
    c2.metric("Method", so["agent_method"] or "none", mark(so["method_agrees"]),
              delta_color="normal" if so["method_agrees"] else "inverse", border=True)
    c3.metric("Agent runs", so["agent_runs"], f"Alloy used {inv.runs_used}", delta_color="off", border=True)
    st.caption(f"Alloy found cause {so['alloy_cause']} and method {so['alloy_method']}.")
    st.text(f"Agent's reason: {so['agent_reason'] or 'not recorded'}")
    return so
