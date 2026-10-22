"""Visual layer for the Streamlit app: research-paper theme, pipeline header, verdict card and figures."""

from html import escape

import altair as alt
import pandas as pd
import streamlit as st

PRIMARY = "#1f3f73"
MUTED = "#cdd5e1"
WARN = "#c2410c"
SANS, MONO = "IBM Plex Sans", "IBM Plex Mono"
STAGES = [
    ("search", "Search", "Bond literature"),
    ("understand", "Understand", "claims + conditions"),
    ("investigate", "Investigate", "reproduce the gap"),
    ("improve", "Improve", "test fixes"),
    ("verify", "Verify", "MirageLab"),
    ("remember", "Remember", "Dead-End Map"),
]
VERDICTS = {
    "resolved": ("Resolved", "ok"),
    "likely_unstated_cause": ("Likely unstated setting", "warn"),
    "insufficient_evidence": ("Insufficient evidence", "muted"),
}

CSS = """<style>
.block-container {padding-top: 2rem; max-width: 1180px;}
h1, h2, h3, [data-testid="stHeading"] :is(h1, h2, h3, h4),
[data-testid="stHeading"] :is(h1, h2, h3, h4) * {
  font-family: 'Source Serif 4', Georgia, serif !important;
  letter-spacing: -0.005em; font-weight: 600 !important;}
.block-container {counter-reset: sec;}
[data-baseweb="tab-panel"] {counter-reset: sec;}
[data-testid="stHeading"] h3::before {counter-increment: sec; content: counter(sec) "."; font-family: 'IBM Plex Mono';
  font-size: 0.8em; color: #8a93a3; margin-right: 0.55em; font-weight: 500;}
.al-hero {border: 1px solid #e4e0d5; border-radius: 6px; padding: 26px 30px 22px; margin-bottom: 8px;
  background-color: #fffefb;
  background-image: linear-gradient(#f1eee6 1px, transparent 1px), linear-gradient(90deg, #f1eee6 1px, transparent 1px);
  background-size: 22px 22px; background-position: -1px -1px;}
.al-top {display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap;}
.al-brand {display: flex; align-items: center; gap: 16px;}
.al-mark {width: 56px; height: 56px; border: 1.5px solid #1f3f73; border-radius: 4px; background: #fffefb;
  position: relative; display: grid; place-items: center; font-family: 'Source Serif 4', serif; font-size: 1.6rem;
  font-weight: 600; color: #1f3f73;}
.al-mark i {position: absolute; top: 3px; left: 5px; font-style: normal; font-family: 'IBM Plex Mono';
  font-size: 0.6rem; color: #6b7280;}
.al-mark u {position: absolute; bottom: 2px; width: 100%; text-align: center; text-decoration: none;
  font-family: 'IBM Plex Mono'; font-size: 0.5rem; color: #6b7280;}
.al-name {font-family: 'Source Serif 4', serif; font-size: 2.2rem; font-weight: 600; color: #141a24; line-height: 1;}
.al-sub {font-family: 'Source Serif 4', serif; font-style: italic; color: #4b5563; font-size: 1.02rem; margin-top: 4px;}
.al-status {display: flex; gap: 8px; flex-wrap: wrap;}
.al-pill {font-family: 'IBM Plex Mono'; font-size: 0.72rem; padding: 4px 10px; border-radius: 3px;
  border: 1px solid #e4e0d5; background: #fffefb; color: #374151; white-space: nowrap;}
.al-dot {display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 6px; background: #9ca3af;}
.al-dot.on {background: #15803d;}
.al-tag {margin: 18px 0 20px; color: #2b3240; font-size: 0.98rem; line-height: 1.6; max-width: 800px;}
.al-tag b {font-variant: small-caps; letter-spacing: 0.06em; color: #1f3f73; margin-right: 6px; font-size: 1.05rem;}
.al-pipe {display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 0; position: relative;
  border-top: 1px solid #e4e0d5; padding-top: 14px;}
.al-stage {position: relative; padding: 0 10px 0 22px;}
.al-stage::before {content: ""; position: absolute; left: 4px; top: 4px; width: 9px; height: 9px; border-radius: 50%;
  border: 1.5px solid #b8bfcb; background: #fffefb;}
.al-stage .n {font-family: 'IBM Plex Mono'; font-size: 0.66rem; color: #9aa2ae;}
.al-stage .t {font-family: 'Source Serif 4', serif; font-weight: 600; color: #6b7280; font-size: 1rem;}
.al-stage .s {font-size: 0.74rem; color: #8a93a3;}
.al-stage.done::before {background: #1f3f73; border-color: #1f3f73;}
.al-stage.done .t {color: #1f3f73;}
.al-stage.stop::before {background: #fff7ed; border-color: #c2410c; box-shadow: 0 0 0 3px #fde4d3;}
.al-stage.stop .t {color: #9a3412;}
.al-verdict {border-left: 4px solid; border-radius: 2px 6px 6px 2px; padding: 16px 22px; margin: 4px 0 6px;
  background: #fffefb; border-top: 1px solid #e4e0d5; border-right: 1px solid #e4e0d5;
  border-bottom: 1px solid #e4e0d5;}
.al-verdict.ok {border-left-color: #15803d;}
.al-verdict.warn {border-left-color: #c2410c;}
.al-verdict.muted {border-left-color: #8a93a3;}
.al-badge {display: block; font-variant: small-caps; letter-spacing: 0.08em; font-size: 0.95rem; font-weight: 600;
  margin-bottom: 6px;}
.ok .al-badge {color: #15803d;} .warn .al-badge {color: #c2410c;} .muted .al-badge {color: #4b5563;}
.al-verdict p {margin: 0; color: #141a24; font-family: 'Source Serif 4', serif; font-size: 1.12rem; line-height: 1.6;}
.al-mode {border-left: 3px solid #1f3f73; background: #fffefb; padding: 10px 14px; color: #374151;
  font-size: 0.9rem; line-height: 1.55; border-radius: 0 4px 4px 0;}
.al-mode b {color: #1f3f73;}
[data-testid="stMetric"] {background: #fffefb;}
[data-testid="stMetricLabel"] p {font-variant: small-caps; letter-spacing: 0.07em; font-size: 0.92rem; color: #4b5563;}
[data-testid="stMetricValue"] {font-family: 'IBM Plex Mono', monospace; font-size: 1.3rem; color: #141a24;}
[data-testid="stMetricValue"] * {white-space: normal !important; overflow: visible !important;
  text-overflow: clip !important; overflow-wrap: anywhere;}
[data-testid="stTabs"] button p {font-family: 'Source Serif 4', serif !important; font-weight: 600;
  font-size: 1.02rem;}
[data-testid="stCaptionContainer"] {color: #5b6472;}
[data-testid="stCaptionContainer"] strong {color: #141a24;}
@media (max-width: 900px) {.al-pipe {grid-template-columns: repeat(3, minmax(0, 1fr)); row-gap: 12px;}}
</style>"""


def inject() -> None:
    st.html(CSS)


def stage_states(inv) -> list[str]:
    if inv is None:
        return ["idle"] * len(STAGES)
    if inv.stage == "done":
        return ["done"] * len(STAGES)
    keys = [key for key, _, _ in STAGES]
    at = keys.index(inv.stage) if inv.stage in keys else 0
    return ["done"] * at + ["stop"] + ["idle"] * (len(STAGES) - at - 1)


def hero(inv, *, model: str, bond_live: bool) -> None:
    stages = "".join(
        f'<div class="al-stage {state}"><div class="n">§{i}</div><div class="t">{title}</div>'
        f'<div class="s">{sub}</div></div>'
        for i, ((_, title, sub), state) in enumerate(zip(STAGES, stage_states(inv), strict=True), start=1)
    )
    st.html(f"""<div class="al-hero">
      <div class="al-top">
        <div class="al-brand"><span class="al-mark"><i>06</i>Ay<u>alloy</u></span>
          <div><div class="al-name">Alloy</div>
          <div class="al-sub">Fuses papers that disagree into a method stronger than either</div></div></div>
        <div class="al-status">
          <span class="al-pill"><span class="al-dot {'on' if bond_live else ''}"></span>Bond
            {'connected' if bond_live else 'offline'}</span>
          <span class="al-pill">model: {escape(model)}</span>
        </div>
      </div>
      <p class="al-tag"><b>Abstract</b>Alloy reads the papers behind a disputed result, reproduces the gap in
        simulation, tests candidate fixes on cases it has never seen, and keeps every source quote and failed run
        open to inspection.</p>
      <div class="al-pipe">{stages}</div>
    </div>""")


def mode_note(text: str) -> None:
    st.html(f'<div class="al-mode">{text}</div>')


def verdict(inv) -> None:
    if inv.verdict is None:
        label, tone, text = "Partial investigation", "muted", "No final verdict was recorded."
    else:
        label, tone = VERDICTS.get(inv.verdict.status, (inv.verdict.status.replace("_", " "), "muted"))
        text = inv.verdict.explanation
    st.html(f'<div class="al-verdict {tone}"><span class="al-badge">Finding · {escape(label)}</span>'
            f"<p>{escape(text)}</p></div>")


def best_method(comparison: dict) -> str | None:
    means = {m: v.get("mean") for m, v in comparison.items() if isinstance(v, dict)}
    means = {m: v for m, v in means.items() if isinstance(v, (int, float))}
    return min(means, key=means.get) if means else None


def _figure(chart):
    return (
        chart.configure_axis(labelFont=SANS, titleFont=SANS, labelColor="#4b5563", titleColor="#4b5563",
                             titleFontWeight=500, gridColor="#ece9e1", domainColor="#c9c4b8", tickColor="#c9c4b8")
        .configure_view(strokeWidth=0)
        .configure(background="transparent")
    )


def comparison_chart(comparison: dict):
    rows = [{"method": m, "mean": v.get("mean"), "worst": v.get("worst")} for m, v in comparison.items()
            if isinstance(v, dict) and isinstance(v.get("mean"), (int, float))]
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df["best"] = df["method"] == best_method(comparison)
    base = alt.Chart(df).encode(y=alt.Y("method:N", sort=alt.EncodingSortField("mean"), title=None,
                                        axis=alt.Axis(labelLimit=260, labelFontSize=12, labelFont=MONO)))
    bars = base.mark_bar(height=16).encode(
        x=alt.X("mean:Q", title="coefficient error — mean over seeds (bar), worst seed (tick)"),
        color=alt.condition("datum.best", alt.value(PRIMARY), alt.value(MUTED)),
        tooltip=["method", alt.Tooltip("mean:Q", format=".3f"), alt.Tooltip("worst:Q", format=".3f")],
    )
    worst = base.mark_tick(thickness=2, size=20, color=WARN).encode(x="worst:Q")
    return _figure((bars + worst).properties(height=40 * len(df) + 30))


def effect_chart(attribution: dict):
    df = pd.DataFrame({"condition": list(attribution), "error added": list(attribution.values())})
    return _figure(alt.Chart(df).mark_bar(height=16, color="#5b7bb0").encode(
        y=alt.Y("condition:N", sort="-x", title=None, axis=alt.Axis(labelLimit=260, labelFont=MONO)),
        x=alt.X("error added:Q", title="error added by changing only this condition"),
        tooltip=["condition", alt.Tooltip("error added:Q", format=".3f")],
    ).properties(height=40 * len(df) + 30))
