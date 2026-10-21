# Multi-paper implementation and acceptance

Updated October 21, 2026. The bounded multi-paper extension is implemented and
committed locally under gods-plan. Full acceptance remains blocked by dependencies,
the absence of a reviewed runnable literature pair, browser/replay access and Work
GitHub write access. No scientific discovery or efficiency gain is established.

## What the workflow does

1. Load a synthetic collection or reviewed evidence bundle.
2. Check work identities and every claim pair; retain exclusions and their reasons.
3. Rank up to three discrepancies, prioritizing explicit condition differences and
   coverage of additional works. Ranking is deterministic, not scientific confidence.
4. Audit the queue under one total run/time budget. Failed runs consume budget;
   partial records remain available; unknown accounting stops later launches.
5. Inspect each pair and export the campaign JSON/Markdown. Child investigations
   are embedded; raw logs and replay notebooks travel as separate run folders.

Hard limits are 20 canonical works, 100 claims and three selected audits. Oversized
inputs, duplicate IDs and nonfinite numbers are rejected explicitly. DOI/arXiv
aliases are normalized; unknown identities remain flagged. No titles are guessed
to be the same work. Each conclusion applies only to its own tested pair.

The campaign currently uses Lorenz/PySINDy. Santosh's adaptive racing, standalone
coatings command and notebook dependencies are integrated through upstream
`6ee33e0d9ddb50e5f6fce59c357b5f9f9fdf6e1b`. The shared Claim/Goal/Budget/
ExperimentSpec/RunResult interfaces are preserved.

## Detailed plan and implementation

[The implementation contract](multi-paper-implementation.md) was committed before
execution. It specifies input gates, ordering, budgets, persistence, failure
semantics, saved-record validation and M1–M8 acceptance. The original
[wave plan](multi-paper-lane-plan.md) remains as a historical planning snapshot.

| Slice | Commit | Result |
| --- | --- | --- |
| Detailed contract | `2fdabc9` | Explicit acceptance and failure cases |
| Upstream integration | `d13acb1` | Actual upstream ancestry, adaptive/coatings preserved |
| Collection screening | `39a042f` | Deterministic queue and visible pair dispositions |
| Campaign execution | `70642a4` | Shared caps/deadline, durable partial records, CLI |
| Independent challenge fixes | `30feb9d` | Consistent statuses, evidence/run references, finite measurements |
| Collection/saved UI | `2bd72b0` | Queue preview, launch, child selection and exports |
| Source review | `526eac6` | Six-paper review and additional protocol blockers |
| Unseen-case failure guard | `019f913` | Failed/nonfinite baselines cannot count as wins |

The controller plan passed its POC workflow check. Controller initialization could
not create `/Users/ganeshmadarasu/.local/state/gods-plan/tasks/20261021-e75faf11`
(`PermissionError`). Execution continued directly in this session using the skill's
fallback, commits, independent review and ignored `.gods-plan/checkpoint.json`.
No background worker or controller is scheduled.

## Acceptance ledger

| ID | Evidence here | Remaining acceptance |
| --- | --- | --- |
| M1 identities/bounds | Alias/query/version, same-work, ambiguous ID, unique IDs, overflow and nonfinite-input checks | Real imported collections beyond the reviewed sample |
| M2 safe screening | Unsupported settings/methods/units/metrics, missing evidence and no-eligible cases rejected or visibly blocked | Reviewed executable literature input |
| M3 deterministic queue | Shuffling preserves selection; two audits cover three synthetic works; selection limits visible | Scientific usefulness of the ranking heuristic |
| M4 shared execution | Mocked runs verify cap redistribution, failed-run charging, expiry, interruption and missing-manifest halt; actual dependency-failure and zero-budget CLI records persist | Actual multi-pair simulation campaign |
| M5 scoped records/report | Saved round trips, ties/n/drop counts, partial/no-verdict states, unknown run references and contradictory statuses checked; valid positive formats and malformed positive verdicts tested | Independent replay of actual measurements |
| M6 UI | Streamlit AppTest checks queue, reviewed refusal, shared budget, saved pair selection, legacy results and exports with execution/path-reading sentinels | Actual browser upload/download walkthrough and notebook replay |
| M7 real science | Six primary works reviewed; three source records retained with explicit protocol gaps | Exact eligible cross-paper pair and its reproducible protocol |
| M8 delivery | Local focused commits, Ruff, whitespace checks and portable patch | Locked installation, full simulations/coatings, browser/replay, publication and feature CI |

Saved uploads are supplied evidence. Validation checks structure, internal
consistency and known references; it does not authenticate measurements or rerun
experiments. Positive verdicts require sampled reproduction and supporting hidden
search or three finite winning unseen cases. Inspecting a saved campaign performs
no experiment, model call or uploaded-path read.

## Verification and environment

The available Python 3.11 environment lacks PySINDy and `tmm`, and has Streamlit
1.30 below the declared minimum. It is not the locked project environment.

* Focused planner/campaign/adaptive/UI/legacy-record checks: **57 passed**,
  14 warnings.
* Full pytest: collection stops at missing `tmm` in `test_tmm_adapter.py`.
* Diagnostic suite excluding only that uncollectable file: **146 passed,
  eight failed**, 14 warnings. The eight failures stem from missing PySINDy
  (four loop scenarios, three adapter checks, one runner assertion seeing the
  dependency error before method validation). This is not a full-suite pass.
* Ruff and `git diff --check` pass.
* Actual CLI plan-only previews three synthetic audits. Zero-run execution saves
  three deferred audits with no child launch. Reviewed input saves an explicit
  zero-audit campaign and performs no synthetic fallback.
* A normal 60-run CLI attempt saved partial records for all three synthetic pairs
  with zero simulations because the adapter dependency is absent. This validates
  dependency-failure persistence only, not the scientific execution path.

`uv sync --cache-dir /private/tmp/alloy-uv-cache` failed while downloading from
`files.pythonhosted.org` because DNS resolution is unavailable. A prior normal
Streamlit launch was denied at socket bind. Neither restriction was bypassed.
No new paid inference or benchmark was run. Historical upstream benchmark and
notebook results do not validate this feature revision.

The independent challenge found and drove fixes for NaN hidden conclusions,
canonical URL aliases, extreme-value overflow, unknown evidence/run references,
contradictory statuses, unsupported positive verdicts and failed-baseline wins.
Budget probes showed no overspending in the tested mocked cases. These results
do not establish that every failure mode or real simulation path is covered.

## Next actions in an enabled environment

```bash
uv sync
uv run pytest -q
uv run ruff check .
uv run alloy campaign --synthetic data/seed/collection_claims.json --plan-only
uv run alloy campaign --synthetic data/seed/collection_claims.json --runs 60 --minutes 5
uv run alloy coatings --layers 3 --tolerance 30
uv run streamlit run ui/app.py
```

In the browser preview synthetic/reviewed collections, run one campaign, switch
between children, export and re-upload its JSON, and inspect partial/deferred
states. Replay one child's notebook and compare recorded metrics:

```bash
uv run jupyter nbconvert --to notebook --execute \
  runs/<campaign>/audits/01/replay.ipynb --output executed.ipynb
```

Keep the scientific work separate: choose one exact published protocol from the
[source review](multi-paper-protocol-review.md), specify its data/library/optimizer/
noise/aggregation/seeds, then extend the adapter if necessary. Do not turn blocked
claims into synthetic substitutes or change author settings to match this adapter.

## Delivery

Branch: `work/knowledge-integrated`. Commits are local. Work GitHub branch creation
previously returned HTTP 403 `Resource not accessible by integration`; no push,
remote feature branch, PR, feature CI, merge or deployment is claimed. The personal
GitHub account was not used.

Portable delivery: `/private/tmp/alloy-multi-paper.patch`, verified against the exact
upstream below. The patch includes the earlier first-lane work and this extension;
it excludes credentials, environment files, caches, runs and local checkpoints.

```bash
git switch -c ganesh/multi-paper 6ee33e0d9ddb50e5f6fce59c357b5f9f9fdf6e1b
git apply --check /path/to/alloy-multi-paper.patch
git apply /path/to/alloy-multi-paper.patch
git diff --stat
```

If upstream moves, review overlap before applying. Keep required simulation,
scientific-input and browser/replay checks open until they have actual evidence.
