"""Real-paper audit: Bond finds and identifies the papers, arXiv supplies the methods text, the
model extracts stated settings, code fills gaps by rule, and the adapter reproduces each paper.

Tiers keep exact and assumed results apart:
  exact                         every setting and the outcome come from the paper text
  reproduced_under_assumptions  reproduces, but some settings or readings are labelled assumptions
  not_reproduced                no reading or one-at-a-time variation matched the reported outcome
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from alloy.config import settings
from alloy.contracts import Budget, ExperimentSpec
from alloy.experiments.export import to_notebook
from alloy.experiments.runner import BudgetExceeded, Runner
from alloy.knowledge import fulltext, protocol
from alloy.knowledge.citations import bibtex
from alloy.knowledge.protocol import Protocol, Setting

DEFAULT_PAIR = ("arxiv:1509.03580", "arxiv:2009.08810")
DEFAULT_QUERY = "SINDy fails at high measurement noise Lorenz"
# Hand-checked answer for the one reviewed pair (docs/real-pair-review.md, finding 1).
TRUTH = {frozenset(DEFAULT_PAIR): "noise placement"}

SEEDS = [0, 1, 2]
# Used when a paper does not state its threshold: a dataset counts as recovered if any value works,
# the rule Kaheman et al. describe for their own sweep.
THRESHOLD_GRID = [0.01, 0.025, 0.05, 0.1, 0.2, 0.4, 0.7, 1.0]
ALTERNATIVES: dict[str, list[Any]] = {
    "derivative": ["exact", "numeric"],
    "ridge": [0.0, 0.05],
    "poly_degree": [2, 3, 5],
    "noise_type": ["gaussian", "outliers"],
}
MAX_VARIANTS = 8
GROUPS = {
    "noise level": ("noise", "noise_scale"),
    "noise placement": ("noise_location", "derivative"),
    "record": ("x0", "dt", "t_end"),
    "library": ("poly_degree",),
    "regression": ("ridge",),
}
Tier = Literal["exact", "reproduced_under_assumptions", "not_reproduced"]


class Attempt(BaseModel):
    label: str
    recovered: float
    matches: bool


class PaperResult(BaseModel):
    paper: str
    title: str | None = None
    url: str | None = None
    outcome: str | None = None
    outcome_noise: str | None = None
    outcome_source: str = "none"
    outcome_quote: str | None = None
    outcome_note: str | None = None
    settings: dict[str, Setting] = Field(default_factory=dict)
    rejected: list[str] = Field(default_factory=list)
    reading: str | None = None
    conditions: dict[str, Any] = Field(default_factory=dict)
    threshold_rule: str = ""
    recovered: float | None = None
    tier: Tier = "not_reproduced"
    assumptions: list[str] = Field(default_factory=list)
    attempts: list[Attempt] = Field(default_factory=list)
    error: str | None = None


class RealPairReport(BaseModel):
    id: str
    papers: list[str]
    query: str
    bond: dict[str, Any] = Field(default_factory=dict)
    results: list[PaperResult] = Field(default_factory=list)
    attribution: dict[str, dict[str, float]] = Field(default_factory=dict)
    deciding: str | None = None
    verdict: str = ""
    truth: str | None = None
    runs_used: int = 0
    notebook: str | None = None


def _recovered(runner: Runner, conds: dict, threshold_stated: bool) -> float:
    """Fraction of seeds that recover exactly the true Lorenz terms."""
    hits = 0
    for seed in SEEDS:
        grid = [conds["threshold"]] if threshold_stated else THRESHOLD_GRID
        for threshold in grid:
            spec = ExperimentSpec(
                task="equations-from-data",
                adapter="pysindy",
                method="sindy",
                conditions={**conds, "threshold": threshold},
                seed=seed,
            )
            result = runner.run(spec)
            if result.ok and result.metrics.get("recovered") == 1.0:
                hits += 1
                break
    return hits / len(SEEDS)


def _matches(outcome: str | None, recovered: float) -> bool:
    return (recovered >= 0.5) if outcome == "recovers" else (recovered < 0.5)


def reproduce(runner: Runner, own: Protocol, other: Protocol, result: PaperResult) -> PaperResult:
    filled = protocol.fill(own, other)
    result.settings = {**filled, **{k: own.settings[k] for k in ("noise_scale",) if k in own.settings}}
    readings = protocol.readings(own)
    if not readings:
        result.error = "no reported outcome with a usable noise level"
        return result
    threshold_stated = "threshold" in filled
    result.threshold_rule = "stated" if threshold_stated else f"unstated: best of {len(THRESHOLD_GRID)} values"
    base = protocol.conditions(filled, readings[0])
    base.setdefault("threshold", 0.1)
    assumed = [f"{k} = {s.value} ({s.source}: {s.note})" for k, s in filled.items() if s.source != "stated"]
    if not threshold_stated:
        assumed.append(result.threshold_rule)
    scale_stated = "noise_scale" in own.settings
    if not scale_stated:
        assumed.append(f"noise read as: {readings[0].label}")
    if result.outcome_source != "text":
        assumed.append(f"outcome read by a reviewer: {result.outcome_quote}")

    def attempt(label: str, conds: dict) -> bool:
        frac = _recovered(runner, conds, threshold_stated)
        ok = _matches(result.outcome, frac)
        result.attempts.append(Attempt(label=label, recovered=frac, matches=ok))
        if ok and result.recovered is None:
            result.recovered, result.conditions, result.reading = frac, conds, label
        return ok

    if attempt(f"paper settings, {readings[0].label}", base):
        exact = not assumed
        result.tier = "exact" if exact else "reproduced_under_assumptions"
        result.assumptions = assumed
        return result
    # Other readings of the noise level, then one assumed setting at a time.
    variants = [
        (f"reading: {r.label}", protocol.conditions(filled, r) | {"threshold": base["threshold"]}) for r in readings[1:]
    ]
    for key, setting in filled.items():
        if setting.source == "stated":
            continue
        for value in ALTERNATIVES.get(key, []):
            if value != setting.value:
                variants.append((f"{key} = {value} instead of {setting.value}", {**base, key: value}))
    for label, conds in variants[:MAX_VARIANTS]:
        if attempt(label, conds):
            result.tier = "reproduced_under_assumptions"
            result.assumptions = assumed + [f"variant: {label}"]
            return result
    result.tier = "not_reproduced"
    result.recovered = result.attempts[0].recovered if result.attempts else None
    result.conditions = base
    result.assumptions = assumed
    return result


def attribute(runner: Runner, good: PaperResult, bad: PaperResult, confirm: bool = True) -> dict[str, dict[str, float]]:
    """Flip each group of settings from the recovering paper to the failing paper's values."""
    effects = {}
    stated = good.threshold_rule == "stated" and bad.threshold_rule == "stated"
    for group, keys in GROUPS.items():
        if all(good.conditions.get(k) == bad.conditions.get(k) for k in keys):
            continue
        forward = {**good.conditions, **{k: bad.conditions[k] for k in keys if k in bad.conditions}}
        reverse = {**bad.conditions, **{k: good.conditions[k] for k in keys if k in good.conditions}}
        after_forward = _recovered(runner, forward, stated)
        # Reverse check: does giving the failing paper the recovering paper's values rescue it?
        after_reverse = _recovered(runner, reverse, stated) if confirm else float("nan")
        effects[group] = {
            "recovered_after_flip": after_forward,
            "effect": good.recovered - after_forward,
            "failing_paper_recovered_after_flip": after_reverse,
        }
    return effects


def _bond_context(papers: list[str], query: str) -> dict[str, Any]:
    """Identify the papers through Valency Bond and check the search finds them."""
    if not (settings.bond_backend == "http" and settings.bond_configured):
        return {"status": "Bond not configured; paper ids used as given"}
    from alloy.knowledge.http_bond import HttpBond

    bond = HttpBond().open()
    ids = [fulltext.arxiv_id(p) or p for p in papers]
    exported = json.loads(bond.call("export_papers_json", {"paper_ids": ids})["content"][0]["text"])
    content = exported.get("content")
    records = json.loads(content) if isinstance(content, str) else content or []
    hits = json.loads(
        bond.call("semantic_search_papers", {"query": query, "limit": 20, "source": "arxiv"})["content"][0]["text"]
    )
    hit_ids = [str(h.get("id", "")).split("v")[0] for h in hits.get("results") or hits.get("papers") or []]
    return {
        "status": "ok",
        "papers": {
            r.get("base_id") or r.get("id"): {
                "title": r.get("title"),
                "doi": r.get("doi"),
                "citations": r.get("citation_count"),
            }
            for r in records
        },
        "search_rank": {pid: (hit_ids.index(pid) + 1 if pid in hit_ids else None) for pid in ids},
    }


def run(
    papers: tuple[str, str] = DEFAULT_PAIR,
    query: str = DEFAULT_QUERY,
    runs: int = 600,
    run_root: Path | None = None,
    use_cache: bool = True,
    save: bool = False,
    confirm: bool = True,
) -> RealPairReport:
    report = RealPairReport(
        id=f"real-pair-{datetime.now():%Y%m%d-%H%M%S-%f}",
        papers=list(papers),
        query=query,
        truth=TRUTH.get(frozenset(papers)),
    )
    run_dir = Path(run_root or settings.run_dir) / report.id
    runner = Runner(Budget(runs=runs, minutes=15), run_dir)
    try:
        report.bond = _bond_context(list(papers), query)
    except Exception as exc:  # noqa: BLE001 - the audit still runs from the ids
        report.bond = {"status": f"Bond lookup failed: {type(exc).__name__}: {exc}"}

    protocols, results = [], []
    for paper in papers:
        committed = protocol.load_committed(paper) if use_cache else None
        if committed is not None:
            proto, url = committed, fulltext.SOURCES[0].format(id=fulltext.arxiv_id(paper))
        else:
            doc = fulltext.fetch(paper, use_cache=use_cache)
            raw, text = protocol.extract(doc, use_cache=use_cache)
            proto, url = protocol.verify(raw, text, paper), doc.url
            if save:
                protocol.save_committed(proto)
        proto = protocol.apply_reviewed_outcome(proto)
        protocols.append(proto)
        meta = report.bond.get("papers", {}).get(fulltext.arxiv_id(paper), {})
        results.append(
            PaperResult(
                paper=paper,
                title=meta.get("title"),
                url=url,
                rejected=proto.rejected,
                outcome=proto.outcome.result if proto.outcome else None,
                outcome_noise=proto.outcome.noise_as_written if proto.outcome else None,
                outcome_source=proto.outcome_source,
                outcome_quote=proto.outcome.quote if proto.outcome else None,
                outcome_note=proto.outcome_note,
            )
        )
    try:
        for i in (0, 1):
            reproduce(runner, protocols[i], protocols[1 - i], results[i])
        report.results = results
        outcomes = {r.outcome for r in results}
        reproduced = [r for r in results if r.tier != "not_reproduced"]
        if outcomes == {"recovers", "fails"} and len(reproduced) == 2:
            good = next(r for r in results if r.outcome == "recovers")
            bad = next(r for r in results if r.outcome == "fails")
            report.attribution = attribute(runner, good, bad, confirm=confirm)
            best = max(report.attribution, key=lambda g: report.attribution[g]["effect"], default=None)
            if best and report.attribution[best]["effect"] >= 0.5:
                report.deciding = best
        report.verdict = _verdict(report)
    except BudgetExceeded as exc:
        report.results, report.verdict = results, f"Stopped early: {exc}"
    finally:
        report.runs_used = runner.runs_used
        runner.save_manifest()
        if runner.results:
            report.notebook = str(
                to_notebook(f"Real pair {' vs '.join(papers)}", runner.results, run_dir / "replay.ipynb")
            )
        (run_dir / "real_pair.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
        (run_dir / "real_pair.md").write_text(to_markdown(report), encoding="utf-8")
    return report


def _verdict(report: RealPairReport) -> str:
    tiers = {r.paper: r.tier for r in report.results}
    missing = [r.paper for r in report.results if r.outcome is None]
    if missing:
        return (
            f"{', '.join(missing)} states no standard-SINDy outcome in its text, so there is nothing to "
            "reproduce. If the result is in a figure or table, a reviewer can add it to "
            "data/literature/reviewed_outcomes.json with its locator."
        )
    if any(t == "not_reproduced" for t in tiers.values()):
        return "At least one paper's reported outcome did not reproduce, so the disagreement is not explained."
    if not report.deciding:
        return "Both papers reproduce, but no single group of settings explains the disagreement."
    effect = report.attribution[report.deciding]
    text = (
        f"Both papers reproduce ({', '.join(f'{p}: {t}' for p, t in tiers.items())}). Moving the "
        f"recovering paper's {report.deciding} to the failing paper's value drops recovery from "
        f"{effect['effect'] + effect['recovered_after_flip']:.2f} to {effect['recovered_after_flip']:.2f}."
    )
    if report.truth:
        text += (
            f" This matches the hand-checked answer ({report.truth})."
            if report.deciding == report.truth
            else f" The hand-checked answer is {report.truth}, so this does not match."
        )
    return text


def to_markdown(report: RealPairReport) -> str:
    out = [
        f"# Real-paper audit: {' vs '.join(report.papers)}",
        "",
        f"**Verdict.** {report.verdict}",
        "",
        f"Runs used: {report.runs_used}. Bond: {report.bond.get('status')}.",
        "",
    ]
    if report.bond.get("search_rank"):
        out += [
            f'Bond semantic search for "{report.query}" ranks: '
            + ", ".join(f"{p}: {r or 'not in top 20'}" for p, r in report.bond["search_rank"].items()),
            "",
        ]
    for r in report.results:
        out += [
            f"## {r.paper}: {r.title or ''}",
            "",
            f"Full text: {r.url}",
            "",
            f"**Tier: {r.tier.replace('_', ' ')}.** Reported outcome: {r.outcome} at noise {r.outcome_noise} "
            f"({'from the text' if r.outcome_source == 'text' else 'read by a reviewer'}: {r.outcome_quote}).",
            "",
        ]
        if r.outcome_note:
            out += [f"Reviewer note: {r.outcome_note}", ""]
        out += ["| Setting | Value | Source | Evidence |", "|---|---|---|---|"]
        for key, s in r.settings.items():
            evidence = (s.quote or s.note or "").replace("|", "\\|")[:160]
            out.append(f"| {key} | {s.value} | {s.source.replace('_', ' ')} | {evidence} |")
        out += ["", f"Threshold: {r.threshold_rule}.", ""]
        if r.assumptions:
            out += ["Labelled assumptions:", ""] + [f"- {a}" for a in r.assumptions] + [""]
        if r.rejected:
            out += ["Rejected extractions:", ""] + [f"- {x}" for x in r.rejected] + [""]
        out += ["| Attempt | Seeds recovered | Matches report |", "|---|---|---|"]
        out += [f"| {a.label} | {a.recovered:.2f} | {'yes' if a.matches else 'no'} |" for a in r.attempts] + [""]
    if report.attribution:
        out += [
            "## Which settings explain the disagreement",
            "",
            "| Group | Recovering paper after flip | Effect | Failing paper after reverse flip |",
            "|---|---|---|---|",
        ]
        out += [
            f"| {g} | {e['recovered_after_flip']:.2f} | {e['effect']:.2f} "
            f"| {e['failing_paper_recovered_after_flip']:.2f} |"
            for g, e in report.attribution.items()
        ] + [""]
    refs = bibtex(report.papers, fetch=True)
    if refs:
        out += [
            "## References",
            "",
            "BibTeX exported from Valency Bond.",
            "",
            "```bibtex",
            "\n\n".join(dict.fromkeys(refs.values())),
            "```",
            "",
        ]
    if report.notebook:
        out += ["Every run is saved next to this file; `replay.ipynb` reruns them.", ""]
    return "\n".join(out)
