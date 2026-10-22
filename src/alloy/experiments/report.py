"""Audit report: one markdown file a reviewer can read to check every step of an investigation."""

from pathlib import Path
from typing import Any

from alloy.knowledge.presentation import evidence_label, paper_url


def _fmt(value: Any) -> str:
    text = "not recorded" if value is None else str(value)
    return text.replace("|", r"\|").replace("\n", "<br>")


def _record(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _sequence(value: Any) -> list:
    return value if isinstance(value, (list, tuple)) else []


def _paper(identifier: Any) -> str:
    identifier = identifier if isinstance(identifier, str) else "not recorded"
    label = identifier.replace("[", r"\[").replace("]", r"\]")
    url = paper_url(identifier)
    return f"[{label}]({url})" if url else label


def _table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(_fmt(c) for c in row) + " |" for row in rows]
    return lines + [""]


def to_markdown(inv, second_opinion: dict[str, Any] | None = None, bibtex: dict[str, str] | None = None) -> str:
    v = inv.verdict
    out = [f"# Audit: {inv.goal.question}", ""]
    if v:
        out += [f"**Verdict: {v.status.replace('_', ' ')}.** {v.explanation}", ""]
    else:
        out += ["**Partial record: no verdict recorded.** This report does not establish a resolved result.", ""]
    if any(c.source == "seed" or "placeholder" in (c.quote or "").lower() for c in inv.claims):
        out += ["**Demo evidence warning:** seed or placeholder claims are not published evidence.", ""]
    out += [f"Investigation `{inv.id}` used {inv.runs_used} of {inv.goal.budget.runs} runs.", ""]

    if second_opinion:
        so = _record(second_opinion)
        def agreement(key):
            return "not recorded" if so.get(key) is None else ("yes" if so[key] else "no")

        out += ["## Second opinion on the agent's answer", ""]
        out += _table(
            ["Item", "Agent said", "Alloy found", "Agree"],
            [
                ["Cause", so.get("agent_cause"), so.get("alloy_cause"), agreement("cause_agrees")],
                ["Method", so.get("agent_method"), so.get("alloy_method"), agreement("method_agrees")],
                ["Runs", so.get("agent_runs"), inv.runs_used, ""],
            ],
        )
        out += [f"Agent's reason: {so.get('agent_reason', 'not recorded')}", ""]

    out += ["## Claims", ""]
    out += _table(
        ["Id", "Paper", "Method", "Quantity", "Value", "Unit", "Outcome", "Conditions"],
        [[c.id, _paper(c.paper), c.method, c.quantity, c.value, c.unit, c.outcome, c.conditions] for c in inv.claims],
    )
    if inv.claims:
        out += ["## Source trail", "",
                "Quotes are supplied evidence; their presence alone is not scientific validation.", ""]
        for claim in inv.claims:
            out += [f"### Claim {claim.id}: {_paper(claim.paper)}", "",
                    f"Source: {claim.source}. {evidence_label(claim)}.", ""]
            out += ["> " + line for line in (claim.quote or "No supporting quote recorded.").splitlines()] + [""]
    if inv.skipped:
        out += ["## Conflicts set aside", ""] + [f"- {s}" for s in inv.skipped] + [""]

    if inv.conflict:
        report = _record(inv.condition_report)
        out += [f"## Condition Check: {inv.conflict[0]} vs {inv.conflict[1]}", ""]
        out += [f"- Comparable: {report.get('comparable')}", f"- Shared: {report.get('shared')}"]
        out += [f"- Differing: {report.get('differing')}"]
        out += [f"- Note: {n}" for n in _sequence(report.get("notes"))] + [""]

    if inv.reproduction:
        out += ["## Reproduction at each paper's stated setting", ""]
        out += _table(
            ["Claim", "Setting", "Mean coef_error", "Runs"],
            [[cid, _record(r).get("conditions"), _record(r).get("coef_error"),
              ", ".join(map(str, _sequence(_record(r).get("run_ids"))))] for cid, r in inv.reproduction.items()],
        )
    if inv.attribution:
        out += ["## Condition attribution", "", "Error added by flipping one condition at a time:", "",
                "One-at-a-time attribution can miss interactions between settings; "
                "it does not prove a unique cause.", ""]
        out += _table(["Condition", "Error added"], [[k, e] for k, e in inv.attribution.items()])
    if inv.hidden_search:
        out += ["## Settings neither paper states", ""]
        out += ["These searches test hypotheses. Matching a number does not establish which settings the authors used; "
                "ask the authors to confirm.", ""]
        out += _table(
            ["Setting", "Value", "Mean coef_error", "Miss vs reported"],
            [[_record(h).get(k) for k in ("condition", "value", "coef_error", "miss")] for h in inv.hidden_search],
        )
    if inv.candidates:
        out += ["## Candidate methods and provenance", "",
                "`engineering_hypothesis` includes unproven combinations. `source_passage` records quote occurrence "
                "in a retrieved paper, not scientific validation of the recommendation.", ""]
        out += _table(
            ["Method", "Rationale", "Evidence status", "Paper", "Source quote"],
            [[_record(c).get("method"), _record(c).get("rationale"),
              _record(c).get("evidence_status", "unknown (legacy record)"),
              _paper(_record(c).get("source_paper")), _record(c).get("source_quote")] for c in inv.candidates],
        )
    if inv.comparison:
        out += [f"## Controlled comparison at {inv.hard_conditions}", ""]
        out += _table(
            ["Method", "Mean", "Worst", "Std error", "n", "Dropped after"],
            [[m, *[_record(s).get(k) for k in ("mean", "worst", "stderr", "n", "dropped_after")]]
             for m, s in inv.comparison.items()],
        )
        out += ["Adaptive racing drops clear losers and samples close methods further. "
                "Surviving alternatives may be tied; unequal sample counts are recorded above.", ""]
    if inv.challenge:
        out += ["## Unseen cases", ""]
        ch = _record(inv.challenge)
        candidate = ch.get("candidate") if isinstance(ch.get("candidate"), str) else "candidate (not recorded)"
        baseline = ch.get("baseline") if isinstance(ch.get("baseline"), str) else "baseline (not recorded)"
        if "candidate" not in ch or "baseline" not in ch:
            out += ["Partial challenge record: candidate or baseline identity is missing.", ""]
        out += _table(
            ["Case", candidate, baseline],
            [
                [
                    {k: val for k, val in _record(c).items() if k not in (candidate, baseline, "run_ids")},
                    _record(c).get(candidate),
                    _record(c).get(baseline),
                ]
                for c in _sequence(ch.get("cases"))
            ],
        )
    if inv.referee:
        out += ["## Referee objections", ""] + [f"- {r}" for r in inv.referee] + [""]

    out += [
        "## Rerun it",
        "",
        ("Run specifications are saved next to this file. Open `replay.ipynb` to rerun the recorded experiments."
         if inv.notebook else "No replay notebook is recorded. "
         "This may be a partial investigation without completed runs."),
        "",
    ]
    if bibtex:
        out += ["## References", "", "BibTeX exported from Valency Bond (`export_papers_bibtex`).", "",
                "```bibtex", "\n\n".join(dict.fromkeys(bibtex.values())), "```", ""]
    return "\n".join(out)


def write(inv, run_dir: Path, second_opinion: dict[str, Any] | None = None, fetch_citations: bool = False) -> Path:
    from alloy.knowledge.citations import bibtex

    refs = bibtex([c.paper for c in inv.claims], fetch=fetch_citations)
    path = Path(run_dir) / "audit.md"
    path.write_text(to_markdown(inv, second_opinion, refs), encoding="utf-8")
    return path
