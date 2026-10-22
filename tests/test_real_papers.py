"""Real-paper pipeline: arXiv HTML parsing, verified extraction, rule-based gap filling, tiers."""

from alloy.agent import real_pair
from alloy.contracts import Budget
from alloy.experiments.runner import Runner
from alloy.knowledge import fulltext, protocol
from alloy.knowledge.protocol import Protocol, ProtocolExtraction, ReportedOutcome, Setting, StatedSetting

HTML = """<html><body><nav>skip me</nav>
<h2 class="ltx_title ltx_title_section">4 Lorenz example</h2>
<p>Data is collected from <math alttext="t=0">t=0</math> to <math alttext="t=100">t</math>
with a time-step of <math alttext="\\Delta t=0.001">dt</math>.</p>
<p>Zero-mean Gaussian noise with variance <math alttext="\\eta">e</math> is added to the derivative.</p>
<figure class="ltx_table"><figcaption>Table 4: Identified coefficients</figcaption>
<table><tr><td>x</td><td>-10.0</td></tr></table></figure>
<h2 class="ltx_title ltx_title_section">References</h2><p>[1] Someone.</p>
</body></html>"""


def test_parse_html_keeps_sections_math_and_tables():
    doc = fulltext.parse_html("1509.03580", "https://arxiv.org/html/1509.03580", HTML)
    titles = [s.title for s in doc.sections]
    assert "4 Lorenz example" in titles and any(t.startswith("Table: Table 4") for t in titles)
    body = next(s.text for s in doc.sections if s.title == "4 Lorenz example")
    assert "\\Delta t=0.001" in body and "skip me" not in body
    assert "-10.0" in next(s.text for s in doc.sections if s.title.startswith("Table:"))


def test_relevant_text_skips_references_and_respects_budget():
    doc = fulltext.parse_html("x", "u", HTML)
    text = fulltext.relevant_text(doc, budget_chars=300)
    assert "Someone" not in text and len(text) <= 320


def test_arxiv_id_only_for_arxiv_papers():
    assert fulltext.arxiv_id("arxiv:2009.08810v2") == "2009.08810"
    assert fulltext.arxiv_id("10.1098/rspa.2021.0904") is None


def test_parse_value_reads_latex_and_units():
    assert protocol.parse_value("x0", "[-8, 7, 27]^T") == [-8.0, 7.0, 27.0]
    assert protocol.parse_value("t_end", "t=0 to t=100") == 100.0
    assert protocol.parse_value("noise", "8%") == 0.08
    assert protocol.parse_value("noise_scale", "var(noise)/var(signal)") == "variance_ratio"


TEXT = (
    "Data is collected from t=0 to t=100 with a time-step of \\Delta t=0.001. "
    "The noise level is defined as \\frac{\\mbox{var}(\\text{Noise)}}{\\mbox{var}(\\text{Signal})} x 100."
)


def test_verify_keeps_quoted_values_and_rejects_unsupported_ones():
    raw = ProtocolExtraction(
        system="lorenz",
        settings=[
            StatedSetting(
                key="dt",
                value="0.001",
                quote="Data is collected from t=0 to t=100 with a time-step of \\Delta t=0.001.",
            ),
            StatedSetting(
                key="noise_scale",
                value="variance_ratio",
                quote=TEXT.split(". ", 1)[1],
            ),
            StatedSetting(
                key="derivative",
                value="numeric",
                quote="Data is collected from t=0 to t=100 with a time-step of \\Delta t=0.001.",
            ),
            StatedSetting(
                key="t_end",
                value="250",
                quote="Data is collected from t=0 to t=100 with a time-step of \\Delta t=0.001.",
            ),
            StatedSetting(key="x0", value="[1, 2, 3]", quote="This sentence is not in the paper at all."),
        ],
    )
    proto = protocol.verify(raw, TEXT, "arxiv:1")
    assert set(proto.settings) == {"dt", "noise_scale"}
    assert len(proto.rejected) == 3


def _proto(paper, **settings):
    return Protocol(
        paper=paper, system="lorenz", settings={k: Setting(value=v, source="stated") for k, v in settings.items()}
    )


def test_fill_never_borrows_noise_placement():
    own, other = _proto("a", dt=0.01), _proto("b", noise_location="derivative", t_end=100.0)
    filled = protocol.fill(own, other)
    assert filled["noise_location"].source == "default" and filled["noise_location"].value == "state"
    assert filled["t_end"].source == "other_paper" and filled["derivative"].source == "rule"


def test_readings_put_the_papers_own_definition_first():
    proto = _proto("k", noise_scale="variance_ratio")
    proto.outcome = ReportedOutcome(result="fails", noise_as_written="10%", quote="q")
    first, second = protocol.readings(proto)
    assert first.label.endswith("var(noise)/var(signal)") and abs(first.noise - 0.1**0.5) < 1e-12
    assert second.noise == 0.1


def _paper(**settings):
    proto = _proto("p", noise_scale="variance", **settings)
    return proto


def test_reproduce_tiers_and_attribution_on_a_quick_pair(tmp_path, monkeypatch):
    monkeypatch.setattr(real_pair, "SEEDS", [0])
    monkeypatch.setattr(real_pair, "THRESHOLD_GRID", [0.1])
    common = dict(x0=[-8.0, 8.0, 27.0], dt=0.002, t_end=5.0, poly_degree=2, noise_type="gaussian", ridge=0.05)
    good = _paper(noise_location="derivative", derivative="exact", **common)
    good.outcome = ReportedOutcome(result="recovers", noise_as_written="1", quote="q")
    bad = _paper(noise_location="state", derivative="numeric", **common)
    bad.outcome = ReportedOutcome(result="fails", noise_as_written="1", quote="q")
    runner = Runner(Budget(runs=200, minutes=5), tmp_path)
    results = []
    for own, other in ((good, bad), (bad, good)):
        res = real_pair.PaperResult(
            paper=own.paper, outcome=own.outcome.result, outcome_source="text", outcome_quote="q"
        )
        results.append(real_pair.reproduce(runner, own, other, res))
    assert [r.tier for r in results] == ["reproduced_under_assumptions"] * 2  # threshold is unstated
    effects = real_pair.attribute(runner, *results)
    assert max(effects, key=lambda g: effects[g]["effect"]) == "noise placement"


HARD = dict(
    system="lorenz",
    x0=[-8.0, 8.0, 27.0],
    dt=0.01,
    t_end=10.0,
    poly_degree=2,
    noise_type="gaussian",
    noise_location="state",
    derivative="numeric",
    noise=0.3,
    noise_scale="state_std",
)


def test_fix_races_methods_checks_unseen_cases_and_keeps_dead_ends(tmp_path, monkeypatch):
    from alloy.agent import real_fix

    monkeypatch.setattr(real_fix, "METHODS", ("sindy", "smoothed-ensemble-sindy"))
    monkeypatch.setattr(real_fix, "THRESHOLDS", (0.1, 0.5))
    runner = Runner(Budget(runs=60, minutes=5), tmp_path / "runs")
    memory = tmp_path / "deadends.jsonl"
    out = real_fix.fix(runner, "arxiv:hard", HARD, memory)
    assert len(out.arms) == 4 and out.winner in {a.label for a in out.arms}
    assert out.baseline and out.baseline.startswith("sindy")
    if not out.winner.startswith("sindy"):
        assert len(out.unseen) == 3 and "unseen trajectories" in out.summary
    dropped = [a for a in out.arms if a.dropped_after is not None]
    assert len(out.dead_ends) == len(dropped)
    if dropped:
        assert memory.exists() and "lost the method race" in memory.read_text(encoding="utf-8")


def test_fix_reports_no_winner_when_budget_runs_out(tmp_path):
    from alloy.agent import real_fix

    out = real_fix.fix(Runner(Budget(runs=3, minutes=5), tmp_path), "arxiv:hard", HARD)
    assert out.winner is None and "budget" in out.summary and not out.verified


def test_fix_claims_no_improvement_when_an_early_dropped_sindy_arm_beats_the_leader(tmp_path, monkeypatch):
    from alloy.agent import real_fix

    def fake_adaptive(runner, specs, start, step, max_seeds):
        stats = {label: {"mean": 0.6, "stderr": 0.05, "n": 3, "dropped_after": 2} for label in specs}
        stats["sindy (threshold 0.2)"] = {"mean": 0.41, "stderr": 0.05, "n": 2, "dropped_after": 2}
        stats["smoothed-ensemble-sindy (threshold 0.2)"] = {"mean": 0.49, "stderr": 0.05, "n": 3, "dropped_after": None}
        return stats, {label: [] for label in specs}, "smoothed-ensemble-sindy (threshold 0.2)"

    monkeypatch.setattr(real_fix.compare, "adaptive", fake_adaptive)
    out = real_fix.fix(Runner(Budget(runs=50, minutes=5), tmp_path), "arxiv:hard", HARD)
    assert "No noise-robust variant clearly beat standard SINDy" in out.summary
    assert "cuts" not in out.summary and not out.unseen and not out.verified


def test_verdict_names_every_group_that_flips_the_result_alone():
    from alloy.agent.real_pair import PaperResult, RealPairReport, _verdict

    report = RealPairReport(
        id="x",
        papers=["arxiv:a", "arxiv:b"],
        query="q",
        results=[
            PaperResult(paper="arxiv:a", outcome="recovers", tier="reproduced_under_assumptions", recovered=1.0),
            PaperResult(paper="arxiv:b", outcome="fails", tier="reproduced_under_assumptions", recovered=0.0),
        ],
        attribution={
            "noise placement": {"recovered_after_flip": 0.0, "effect": 1.0},
            "record": {"recovered_after_flip": 0.0, "effect": 1.0},
            "noise level": {"recovered_after_flip": 0.67, "effect": 0.33},
        },
        deciding="noise placement",
    )
    assert report.causes == ["noise placement", "record"]
    text = _verdict(report)
    assert "Moving its record length alone also drops recovery from 1.00 to 0.00" in text
    assert "cannot name a single cause" in text and "noise level alone" not in text
