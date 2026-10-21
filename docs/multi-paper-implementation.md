# Multi-paper implementation contract

Approved scope: user instruction on October 21, 2026, “lets make a more detailed
plan so you dont make more mistakes and then use gods-plan to impl”. This refines
[the lane plan](multi-paper-lane-plan.md), reusing its local implementation and
commit authorization. No paid inference, deployment or remote merge is included.

This is a reversible hackathon POC. Its hypothesis is that a small literature
collection can produce several inspectable, scoped audits under one budget.
Success requires deterministic screening, safe evidence gates, bounded execution
and useful saved records. It does not require a positive scientific discovery.
Real-paper reproduction, browser verification and publication remain separate
acceptance items when their inputs or environment are unavailable.

## User flow and non-goals

1. Load a reviewed EvidenceBundle or explicitly synthetic Claim collection.
2. Preview canonical works, every pair's disposition and a queue of up to three.
3. Set one total run/time budget; execute the queue offline.
4. Inspect each pair's conditions, source trail, measurements and conclusion.
5. Export a campaign containing embedded child records and a Markdown summary.
   Transfer local run folders separately for notebooks and raw simulation logs.

Bond metadata remains discovery input, never automatic reproduction evidence.
No arbitrary uploaded non-seed claims become runnable without a validated reviewed
bundle. No generic science engine, automatic protocol invention, resume/retry,
parallel simulations or coatings literature pipeline is added in this version.

## Stable interfaces and ownership

Preserve Claim, Budget, Goal, ExperimentSpec, RunResult and legacy Investigation
JSON. Add separate models in `knowledge/collection.py` and `agent/campaign.py`.
The coordinator calls the existing pair investigation with exactly two claims,
offline=True and referee=False. Add optional keyword-only output-directory support
to `investigate` so each child has an unambiguous durable location. Its default
single-pair behavior remains unchanged. No controller or second lead edits the
same worktree concurrently.

Integrate upstream through `6ee33e0` first. Preserve adaptive seed racing, sample
counts, dropped methods, ties, coatings and replay dependencies. Restrict necessary
shared fixes to comparison edge cases and pair output routing. Preserve the local
measurement guards and baseline's complete Claim input.

## M1–M3: collection and planner contract

`plan_collection(claims, *, evidence=None, max_audits=3)` returns a versioned
CollectionPlan. It stores original Claims; canonical work ID per claim; provenance
and source locations from an optional validated bundle; identity warnings; limits;
input/retained/excluded counts; all screened PairPlans; ordered selected pair IDs.

* Reject duplicate or empty claim IDs, invalid max_audits, and more than 100 input
  claims or 20 canonical works. Hard rejection is explicit; no silent truncation.
  Validate before generating the quadratic pair list (at most 4,950 pairs).
* Reject nonfinite numbers, including nested condition values, before export can
  convert NaN/Infinity into null and change screening on reload.
* Normalize explicit DOI URLs/prefixes case-insensitively and arXiv abs/pdf URLs,
  arXiv prefixes and version suffixes. Do not guess DOI/arXiv cross-identities from
  titles. Unknown IDs retain their trimmed spelling and get an identity warning.
* Different claims, quotes and numbers remain separate even for the same work.
  Same canonical work pairs are incompatible as independent cross-paper evidence.
* Sort claims by unique ID and store pair IDs as an unambiguous encoding of those
  two IDs; do not depend on insertion order or concatenate with unsafe delimiters.
* Each pair has one disposition: incompatible, blocked_evidence,
  no_detected_discrepancy, eligible or deferred; reasons are mandatory.
* First reject mismatched method, metric, unit or system using Condition Check.
  Then validate the supported Lorenz measurement/method profile and settings.
  Exact reviewed claims need all six supported settings and matching reviewed
  implementation. Synthetic claims may use the existing default-setting path,
  clearly labeled as assumptions, but unsupported supplied keys/values are blocked.
* For literature, only claims from the supplied bundle whose source is marked
  eligible and passes execution_issue are runnable. Quote occurrence is provenance
  validation, not independent confirmation of the paper's scientific result.
* Numeric discrepancy: abs(a-b)/max(abs(a),abs(b),1e-9) > 0.25. Qualitative:
  normalized outcomes differ. Mixed numeric/qualitative forms are incompatible.
  This is screening, not a statistical contradiction test.
* Greedy selection key, recalculated after each pick: explicit supported condition
  differences first; number of newly covered canonical works descending; relative
  gap descending; pair ID ascending. Reasons record actual coverage and gap.
  Remaining eligible pairs become deferred with selection-limit reason.

## M4: execution, persistence and accounting

`run_campaign(goal, plan)` validates the plan before running, creates a UUID-based
campaign directory and stores `campaign.json` plus `campaign.md`. A child lives in
`audits/<pair-index>/`, with the existing investigation, manifest, runs and notebook.
Paths in the summary are relative, informational and never dereferenced on upload.

Campaign fields: kind='campaign', version=1, ID, Goal, CollectionPlan, audit entries,
status, elapsed_seconds, runs_used and errors. Each entry stores pair ID, status,
allocated cap, consumed count, portable run-ID inventory, relative directory, optional embedded Investigation
and error. Status is pending/running/complete/partial/failed/deferred. Complete
means a recorded verdict and trustworthy run accounting, not scientific resolution.

* Reject nonpositive/nonfinite time, negative runs, non-Lorenz Goal adapter/task,
  and inconsistent plans. Zero runs is a valid preview-only/deferred campaign.
* At each launch, remaining runs = original total minus verified consumption.
  Cap = floor(remaining runs / remaining selected pairs). Redistribution uses only
  verified unspent runs from previous children; no child exceeds its assigned cap.
* Minimum launch cost is six reproduction runs when conditions differ, three when
  identical (the loop reuses those runs). If the fair cap is below that minimum,
  defer that pair with a reason and do not call investigate.
* Pass the shared deadline's remaining minutes to the child. Recheck deadline
  before every child. The Runner checks time before each simulation; an in-flight
  simulation may finish late. Do not claim a hard process deadline.
* Persist the running entry before execution, then after every outcome. Use atomic
  JSON replacement. An interruption leaves status='running', never fabricated
  completion. There is no automatic resume or retry; a new campaign is a new,
  explicit execution, not continuation with a free reset.
* Reconcile manifest length against child runs_used, allocated cap and run files.
  Failed simulations count. On exception load the saved partial Investigation and
  manifest where available. Missing/malformed/inconsistent accounting stops later
  launches; mark remaining pairs deferred for accounting failure. Preserve errors.
* Catch ordinary child exceptions to retain partial evidence. Persist and re-raise
  interruption signals after reconciliation. Never swallow KeyboardInterrupt.
* Empty input produces an inspectable zero-audit campaign, not synthetic fallback.

## M5–M6: reporting, saved records and UI

The report states input/retained works and claims, selected/attempted/completed/
partial/deferred pairs and total consumption. Every verdict identifies its pair.
A/B results never settle A/C or establish a globally best method. Include the
screening caveat, synthetic warning, rejection reasons, ties, n, stderr and drop
counts in child reports. Partial records retain no-verdict and failed-case labels.

Add `alloy campaign` with mutually exclusive `--synthetic PATH` and `--evidence
PATH`, `--plan-only`, `--runs`, `--minutes`, `--max-audits` and `--question`.
Synthetic input is a list of Claims and must contain only source='seed'. No online
flag. Existing demo/audit/bench/coatings commands remain available.

Add a collection mode to the current UI with synthetic/reviewed selection, visible
queue, shared budget and Run campaign button. Add a saved campaign mode; uploads
are limited to 5 MB, validated by kind/version and cross-record references. Saved
records only render; they never trigger a model, simulator, subprocess or file path
read. Embed child Investigations to make transferred records inspectable without
the original disk. Select one child for the existing investigation viewer.

Reject missing/duplicate/unknown pair or claim references, inconsistent selection,
negative/nonfinite counts and malformed embedded child records. Forbid unknown
campaign/planner fields. Download JSON/Markdown from validated objects. Existing
single-investigation notebook download remains restricted to the configured local
run root; saved campaigns do not dereference notebook paths. Validate positive
verdicts against sampled reproduction, hidden-search or unseen-challenge records;
saved measurements remain supplied evidence, not independent verification. Clear stale
result state on mode changes so a prior result cannot masquerade as a new campaign.

## M7–M8 and ordered tasks

| Task | Depends on | Files / output | Required verification |
| --- | --- | --- | --- |
| T0 | contract | integrate upstream; overlap review | exact upstream ancestry, existing knowledge tests, adaptive/coatings tests |
| T1 | T0 | collection.py, test_collection.py | M1–M3: aliases, same work, shuffling, missing settings, nonfinite numbers, unsupported methods, bounds, no eligible pairs |
| T2 | T1 | campaign.py, loop output argument, comparison edge fix | M4: shared caps, early return redistribution, failed run count, budget/time expiry, missing manifest, interruption, no child on empty input |
| T3 | T2 | campaign report/record parser, CLI and synthetic fixture | M5: scoped conclusions, adaptive n/drop/tie fields; CLI plan-only performs no execution |
| T4 | T3 | ui/app.py, campaign UI tests | M6: legacy result regression, saved campaign no execution, malformed upload, safe exports, child selection |
| T5 | parallel bounded research | reviewed source evidence and protocol-gap notes | M7 remains open unless an exact runnable reviewed cross-paper pair exists; never substitute seed claims |
| T6 | T0–T5 | handoff, checks and portable delivery | M8: locked install, full pytest/Ruff, real offline campaign, notebook replay, actual browser, publication status |

T5 reuses the three reviewed primary sources first. Search at most 20 relevant
primary works, recording any additional review and actual protocol compatibility.
Do not alter a paper's reported settings to fit the adapter. A larger adapter
extension requires its own explicit protocol design. Scientific novelty and improved
efficiency remain unestablished without measured evidence.

## Execution and rollback

Commit this contract before implementation. Validate the structured snapshot at
`/private/tmp/alloy-multi-paper-controller.json`, attempt the installed controller
using existing authorization, and otherwise execute directly under gods-plan if
its protected state directory remains inaccessible. Record the limitation and
current evidence in the ignored checkpoint. Do not bypass denied access.

Commit coherent integration/planner/coordinator/UI slices with their checks. New
behavior can be rolled back by reverting those commits; no external migrations or
services are involved. Final review compares every M1–M8 to actual evidence and
reports blocked acceptance distinctly from implemented code. A patch must be
apply-checked against the exact integrated upstream head if Work publication is
still unavailable. No full acceptance claim based solely on mocked simulations.
