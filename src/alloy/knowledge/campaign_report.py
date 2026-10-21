"""Portable reports never dereference paths supplied by saved campaigns."""

from alloy.experiments.report import _fmt, _table, to_markdown


def campaign_markdown(campaign) -> str:
    plan = campaign.plan
    counts = {s: sum(e.status == s for e in campaign.audits)
              for s in ("complete", "partial", "failed", "deferred", "pending", "running")}
    attempted = sum(e.allocated_runs > 0 for e in campaign.audits)
    out = [f"# Collection audit: {_fmt(campaign.goal.question)}", "",
           f"Campaign `{campaign.id}`: **{campaign.status}**.", "",
           f"{len(plan.claims)} claims across {len(set(plan.canonical_works.values()))} canonical works; "
           f"{len(plan.pairs)} screened pairs; {len(plan.selected)} selected; {attempted} attempted.", "",
           f"Audit states: {_fmt(counts)}.", "",
           f"Recorded consumption: {campaign.runs_used}/{campaign.goal.budget.runs} runs; "
           f"{campaign.elapsed_seconds:.2f} seconds. Accounting complete: {campaign.accounting_complete}.", "",
           "Failed simulations count. An in-flight simulation may finish after the shared deadline.", "",
           "A point-value gap is a screening heuristic, not a statistically established contradiction. "
           "Each conclusion applies only to its own claim pair and tested settings. "
           "No global best method or untested pair is established.", ""]
    if any(c.source == "seed" for c in plan.claims):
        out += ["**Synthetic demonstration:** seed claims are not published evidence.", ""]
    if not campaign.accounting_complete:
        out += ["**Accounting failure:** recorded consumption is a known subtotal, not a verified total. "
                "No later audits were launched.", ""]
    out += ["## Pair screening", ""]
    out += _table(["Pair", "Disposition", "Reasons", "Queue rationale"],
                  [[p.claims, p.disposition, "; ".join(p.reasons), "; ".join(p.ranking_reasons)] for p in plan.pairs])
    for entry in campaign.audits:
        out += [f"## Audit {_fmt(entry.pair_id)}", "",
                f"Status: {entry.status}; allocated: {entry.allocated_runs}; consumed: {entry.runs_used}.", "",
                f"Artifact directory (transfer separately): `{entry.directory}`. "
                "Contains investigation.json, audit.md, manifest.json and replay.ipynb when generated.", ""]
        if entry.error:
            out += [f"Recorded error: {_fmt(entry.error)}", ""]
        if entry.investigation:
            out += [to_markdown(entry.investigation), ""]
    if campaign.errors:
        out += ["## Campaign errors", ""] + [f"- {_fmt(e)}" for e in campaign.errors]
    return "\n".join(out)
