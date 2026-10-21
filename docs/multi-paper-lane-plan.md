# Finish the knowledge/UI lane: multi-paper audits

Prepared October 21, 2026 under gods-plan. This is the historical planning snapshot
for the bounded hackathon POC. Implementation has since proceeded under the
[detailed contract](multi-paper-implementation.md); consult the
[current acceptance ledger](multi-paper-handoff.md) for actual completion and blockers.
The observations below describe the state when this plan was prepared.

## Desired result

A researcher gives Alloy a question and a collection of papers. Alloy shows which
claims can be compared, ranks the discrepancies worth investigating, audits several
within one compute budget, and produces a source-linked report. Every conclusion
applies to its own claims, methods and tested settings.

The contribution we are testing is an inspectable audit across a small research
collection. More papers alone do not establish novelty, correctness or a speedup.

## Current evidence and scope

- Our local branch is `work/knowledge-integrated`, head `3524bd1`, with upstream
  integrated through `fec698e`. It has knowledge validation, reviewed-source
  inspection, method provenance, saved-result UI and audit exports.
- GitHub inspected for this plan is at
  [`6ee33e0`](https://github.com/santoshnymbl/alloy/commit/6ee33e0d9ddb50e5f6fce59c357b5f9f9fdf6e1b).
  Four newer commits add adaptive method racing (`153eedf`), cooling coatings and
  the registry fix (`84c0b35`), coatings documentation (`e007ea5`), and notebook
  execution dependencies (`6ee33e0`). These changes are inspected, not locally integrated.
- The existing graph accepts many claims and the upstream `many_papers` scenario
  has ten. The loop nevertheless stops at the first comparable discrepancy.
  Multi-paper collection and multi-discrepancy execution are separate requirements.
- The graph currently compares all claim pairs by method and quantity; downstream
  checks reject traps. It needs explicit distinct-work handling and a visible
  compatibility/ranking result before a collection can be audited reliably.
- Three primary papers are reviewed, but the evidence bundle has zero executable
  claims and no eligible cross-paper pair. This remains a scientific input gap.
- Previous local verification: 98 tests passed, eight failed due to missing
  PySINDy; Ruff passed. Those results do not cover this plan or newer upstream code.
- Work GitHub branch creation returned 403. Dependency downloads, local socket
  binding and controller state-directory creation failed in this managed session.
  Do not retry denied actions through a different interface. Cached ingestion,
  local planning and isolated code checks remain usable.

Keep the first implementation on the supported Lorenz/PySINDy literature path.
Preserve Santosh's standalone coatings command and its approximate-optics caveats;
the current investigation loop and measurement gate are Lorenz-specific. Supporting
full multi-paper investigations for coatings requires a separately specified metric
and protocol path, not relabeling the Lorenz loop as adapter-independent.

## Ownership and files

| Area | Owner and intended change |
| --- | --- |
| `knowledge/graph.py`, new collection/planning module | Ganesh: canonical works, evidence groups, eligible discrepancies and ranking |
| `knowledge/source_bundle.py`, reviewed source data | Ganesh: source eligibility and reviewed experiment specifications |
| `ui/app.py`, saved-record parsing | Ganesh: collection overview, ranked audit queue and selected audit details |
| New campaign coordinator and campaign report | Ganesh with explicit shared integration review: wrap existing pair investigations |
| `agent/loop.py`, adapters, adaptive comparison, verification | Santosh's existing implementation; integrate and preserve, make only necessary shared fixes |
| `contracts.py`, baseline and CLI | Shared: preserve Claim/ExperimentSpec/RunResult interfaces; review any additional changes explicitly |

## Bounded design

### Collection and comparisons

Start with at most **20 distinct works and 100 claims**, imported from cached/native
Bond responses or a reviewed bundle. Make limits visible; retain truncation counts.
Keep original identifiers, canonical identifiers, provenance and source locations.
Deduplicate known DOI/arXiv aliases and repeated passages without silently merging
different numerical results. Ambiguous identities stay flagged rather than guessed.
Claim IDs must be unique and deterministic; a collision is an input error.

Compare within explicit method, metric, unit, system and implementation profiles.
Conditions the adapter can vary may differ. Missing values and unsupported settings
remain evidence gaps. Claims from the same canonical work are not independent
cross-paper comparisons. Different methods are candidates for controlled method
comparison, not evidence that a condition caused a published discrepancy.

Use the existing discrepancy threshold initially, documented as a configurable
screening heuristic. A difference in point values is not a statistically established
contradiction. Where uncertainties or compatible metrics are unavailable, say so.
Matching results are recorded as no detected discrepancy, not proof of agreement.

Every screened pair gets an inspectable disposition: no detected discrepancy,
incompatible, blocked by evidence, eligible or deferred. Keep individual claims and
rejection reasons visible so grouping does not hide inconvenient results.

### Queue and budget

Rank eligible pairs deterministically: explicit supported condition differences
before unstated-setting hypotheses, then coverage of source works not yet selected,
then normalized discrepancy magnitude, with stable IDs breaking ties. Show these
reasons rather than an invented scientific confidence score. Source coverage is
coverage only; it does not establish independent replication.

Select at most **three audits** for the first version. One campaign owns the total
run and time budget. Preserve the existing 60-run default; do not turn it into 60
runs per pair. Allocate bounded child budgets before calling the existing loop,
redistribute only verified unused runs, and stop launching work at the shared
deadline. The current runner checks time before starting each simulation; one
in-flight simulation can finish after the deadline. Do not advertise a hard kill.

Three audits may be partial under 60 total runs. A local demonstration can explicitly
choose 180 total runs to allow up to 60 per audit. The UI/CLI must show this choice.
Never start an audit that cannot afford its minimum reproduction phase. Mark the
remaining pairs deferred for budget, with the reason visible.

### Execution and records

Add a coordinator around `investigate(claims=[a, b], ...)`, preserving Santosh's
pair-level reproduction, method racing, unseen verification and notebook export.
Keep Campaign records separate from Investigation records; do not overload a
single `conflict` field to represent an entire literature collection.

The campaign record contains source/claim IDs, planning dispositions, ranking
reasons, selection, child run caps, result paths, consumed runs, elapsed time and
per-audit complete/partial/failed/deferred status. Save after each child and on
failure. If a child raises, retain its saved partial record and reconcile actual
consumption before proceeding. Stop if budget accounting cannot be established.
Failed simulations count against the budget. A retry gets no free budget reset.

The campaign report links to per-audit JSON, Markdown, run manifests and notebooks.
It states how much of the collection was actually tested. A result for A/B does
not settle B/C or imply a global winning method. Keep ties, missing verdicts,
contradictory local outcomes and untested regions visible.

## Implementation waves

| Wave | Work and dependency | Reviewable output | Exit check |
| --- | --- | --- | --- |
| 0: Align code | Integrate the four inspected upstream commits; preserve local evidence guards, baseline correction, commands and audit/UI work | Focused integration commit and overlap notes | Adaptive comparison fields `n`/`dropped_after`, coatings, replay deps and existing knowledge behavior coexist; no paid rerun |
| 1: Plan the collection | Implement canonical work/claim identity, compatibility dispositions and deterministic ranking; depends on wave 0 interfaces | Planner module, portable plan JSON and rejection explanations | A shuffled multi-paper fixture produces the same queue; aliases, same-work pairs and incompatible claims are handled visibly |
| 2: Execute several audits | Add the bounded campaign wrapper and persistent accounting; depends on wave 1 | Campaign JSON, per-pair results, partial/failure recovery | At least two discrepancies involving at least three distinct synthetic works are attempted under one budget; no run/time-budget reset per pair |
| 3: Show the evidence | Add collection counts, eligible/blocked/deferred views, queue preview, audit selector and campaign exports; depends on record formats from waves 1–2 | Streamlit collection/campaign views with legacy result support | Saved campaigns load without simulation or model calls; each verdict links to its own sources, conditions and child exports |
| 4: Establish real input | Review primary papers and associated data/scripts; begin alongside waves 1–3 | An exact supported protocol and reviewed eligible real-paper pair, or a documented unresolved protocol gap | Every runnable claim has source passage, location, metric/units, stated settings and matching implementation; synthetic fixtures stay labeled |
| 5: Verify and deliver | Full checks, bounded offline campaign, browser and replay walkthrough, then publish through Work access or prepare updated patches | Final acceptance ledger, shareable report, focused commits and publication status | Code, scientific input, actual UI/replay behavior and publication each have explicit evidence; blocked checks remain open |

Wave 4 is not replaced by a synthetic demo. Review a bounded set of up to 20
relevant primary works, then record whether the obstacle is missing data, incompatible
metrics, missing protocol details or adapter mismatch. If no pair is eligible, retain
the reviewed evidence and leave real-literature acceptance open. Any larger adapter
extension gets an explicit protocol design before implementation.

## Acceptance scenarios

| ID | Given / when / then | Verification |
| --- | --- | --- |
| M1 | Given duplicate index records and more than two papers, when importing, then canonical works and source passages are preserved, distinct counts are correct and limits are visible | Known DOI/arXiv alias, ambiguous ID, duplicate claim and overflow fixtures |
| M2 | Given differing methods, metrics, units, systems and incomplete protocols, when screening, then no unsafe pair becomes executable and every exclusion has a reason | Planner and condition-check tests; zero eligible-pair case |
| M3 | Given several eligible discrepancies, when input order changes, then ranking/selection is reproducible and two audits can cover at least three works | Deterministic queue test with cross-paper coverage; same-work rejection |
| M4 | Given a shared run/time budget, when audits succeed, fail or exhaust it, then total consumption stays bounded, partial records remain inspectable and deferred pairs remain visible | Fake-runner accounting tests, no-budget/time-expired/all-failed cases; actual offline campaign after install |
| M5 | Given ties, dropped methods, partial verification and unseen-case failures, when reporting, then the UI and report retain uncertainty, sample counts, drop reasons and per-pair scope | Saved campaign fixtures and adaptive-comparison integration checks |
| M6 | Given legacy Investigation JSON and new Campaign JSON, when opening saved results, then both render without experiment/model calls; exports reference the correct run files | Streamlit AppTest plus manual upload/download and local notebook replay |
| M7 | Given a reviewed real-paper pair, when running its stated protocol, then assumptions and measurement differences are explicit and results are reproducible | Primary-source review, recorded simulation specs, metrics and notebook replay; remains open if no eligible pair |
| M8 | Given the combined branch, when another developer installs and runs the documented flow, then it works without paid inference and has precise delivery status | Locked install, full pytest/Ruff, offline campaign, browser walkthrough and CI on the actual published revision |

Challenge the scheduler beyond its happy path: zero eligible pairs; one compatible
pair; three selected pairs with insufficient runs; budget exhaustion during a child;
malformed saved data; duplicate work aliases; a failing simulator; all method scores
nonfinite; and an interrupted campaign. Catch child failures without fabricating a
successful audit. Preserve old CLI commands and saved single-investigation records.

## Validation and delivery

Use the integrated lockfile with `uv sync`, then `uv run pytest -q` and
`uv run ruff check .`. Run `alloy demo`, a bounded campaign and the existing
`alloy bench --alloy-only`; preserve upstream coatings smoke checks. Execute a
recorded notebook with the newly added notebook dependencies and compare recorded
metrics. Recheck updated CI against the actual feature revision, not Santosh's
earlier main revision.

Keep paid `audit`, online extraction/referee and plain-agent benchmarks outside
execution permission. Do not claim updated speed or accuracy from historical
results. Keep the original baseline fairness correction when integrating.

Start publication/access and dependency-environment resolution alongside wave 0 so
they cannot quietly become last-step surprises. A 403 is an access blocker, not
permission to use the personal GitHub connection. Do not create a ready-for-review
PR before required verification passes. Prepare an apply-checked patch against the
new integrated upstream revision if publication remains unavailable; the existing
patch is based on `fec698e` and cannot be assumed to apply to the new head.

Commit each coherent wave with its tests and update the handoff. This planning turn
does not launch a background controller or new implementation run. Reuse existing
implementation authorization on execution; record the amended multi-paper contract
before starting sustained work, and use the controller only if its required state
directory is writable. Otherwise continue directly with an accurate checkpoint.
