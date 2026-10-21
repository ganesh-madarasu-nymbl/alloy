"""Audit report: one markdown file a reviewer can read to check every step of an investigation."""

from pathlib import Path
from typing import Any


def _fmt(value: Any) -> str:
    return f"{value:.3f}" if isinstance(value, float) else str(value)


def _table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(_fmt(c) for c in row) + " |" for row in rows]
    return lines + [""]


def to_markdown(inv, second_opinion: dict[str, Any] | None = None) -> str:
    v = inv.verdict
    out = [f"# Audit: {inv.goal.question}", ""]
    if v:
        out += [f"**Verdict: {v.status.replace('_', ' ')}.** {v.explanation}", ""]
    out += [f"Investigation `{inv.id}` used {inv.runs_used} of {inv.goal.budget.runs} runs.", ""]

    if second_opinion:
        so = second_opinion
        out += ["## Second opinion on the agent's answer", ""]
        out += _table(
            ["Item", "Agent said", "Alloy found", "Agree"],
            [
                ["Cause", so["agent_cause"], so["alloy_cause"], "yes" if so["cause_agrees"] else "no"],
                ["Method", so["agent_method"], so["alloy_method"], "yes" if so["method_agrees"] else "no"],
                ["Runs", so["agent_runs"], inv.runs_used, ""],
            ],
        )
        out += [f"Agent's reason: {so['agent_reason']}", ""]

    out += ["## Claims", ""]
    out += _table(
        ["Id", "Paper", "Method", "Result", "Conditions"],
        [[c.id, c.paper, c.method, c.outcome or c.value, c.conditions] for c in inv.claims],
    )
    if inv.skipped:
        out += ["## Conflicts set aside", ""] + [f"- {s}" for s in inv.skipped] + [""]

    if inv.conflict:
        report = inv.condition_report
        out += [f"## Condition Check: {inv.conflict[0]} vs {inv.conflict[1]}", ""]
        out += [f"- Comparable: {report.get('comparable')}", f"- Shared: {report.get('shared')}"]
        out += [f"- Differing: {report.get('differing')}"] + [f"- Note: {n}" for n in report.get("notes", [])] + [""]

    if inv.reproduction:
        out += ["## Reproduction at each paper's stated setting", ""]
        out += _table(
            ["Claim", "Setting", "Mean coef_error", "Runs"],
            [[cid, r["conditions"], r["coef_error"], ", ".join(r["run_ids"])] for cid, r in inv.reproduction.items()],
        )
    if inv.attribution:
        out += ["## Which condition causes the gap", "", "Error added by flipping one condition at a time:", ""]
        out += _table(["Condition", "Error added"], [[k, e] for k, e in inv.attribution.items()])
    if inv.hidden_search:
        out += ["## Settings neither paper states", ""]
        out += _table(
            ["Setting", "Value", "Mean coef_error", "Miss vs reported"],
            [[h["condition"], h["value"], h["coef_error"], h["miss"]] for h in inv.hidden_search],
        )
    if inv.comparison:
        out += [f"## Controlled comparison at {inv.hard_conditions}", ""]
        out += _table(
            ["Method", "Mean", "Worst", "Std error"],
            [[m, s["mean"], s["worst"], s.get("stderr", "-")] for m, s in inv.comparison.items()],
        )
    if inv.challenge:
        out += ["## Unseen cases", ""]
        ch = inv.challenge
        out += _table(
            ["Case", ch["candidate"], ch["baseline"]],
            [
                [
                    {k: c[k] for k in c if k not in (ch["candidate"], ch["baseline"], "run_ids")},
                    c[ch["candidate"]],
                    c[ch["baseline"]],
                ]
                for c in ch["cases"]
            ],
        )
    if inv.referee:
        out += ["## Referee objections", ""] + [f"- {r}" for r in inv.referee] + [""]

    out += [
        "## Rerun it",
        "",
        "Every run's spec is saved next to this file. Open `replay.ipynb` to rerun them all.",
        "",
    ]
    return "\n".join(out)


def write(inv, run_dir: Path, second_opinion: dict[str, Any] | None = None) -> Path:
    path = Path(run_dir) / "audit.md"
    path.write_text(to_markdown(inv, second_opinion), encoding="utf-8")
    return path
