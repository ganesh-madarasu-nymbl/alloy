# Ganesh's first-lane handoff

Updated October 21, 2026. Knowledge, UI and audit integration are implemented and
committed locally. Full acceptance is still open: real-paper reproduction,
simulation checks, browser interaction and publication remain unverified.

## What Santosh can use

- Bond raw-result import, duplicate-work removal and cached replay without paid inference.
- A reviewed source bundle with three primary papers, excerpts, source locations,
  stated settings and concrete reproduction gaps.
- Condition Check distinguishes incompatible measurements, missing evidence,
  runnable differences and hypotheses about unstated settings. Multiple supported
  conditions may differ; one-at-a-time attribution does not exclude interactions.
- Method candidates carry retrieved-source quotations or an explicit engineering
  hypothesis label. Unsupported methods and fabricated source quotations are rejected.
- The UI displays reviewed evidence, saved or partial investigations, skipped pairs,
  comparisons, uncertainty, unseen cases and filterable failure history. Viewing a
  saved investigation does not rerun experiments. Audit, graph and record downloads
  are available; notebook downloads are restricted to the local run directory.
- Santosh's latest auditor report and CLI remain intact. Reports now preserve
  source evidence, candidate provenance, zero values and partial-record warnings.
- The baseline prompt now receives every Claim field, including units. Historical
  upstream benchmark results predate this correction and were not rerun here.

## Integration and ownership

Branch: `work/knowledge-integrated`. Integrated upstream:
`fec698ed0300ff142026f1ee90971ca0e7250da5` from `santoshnymbl/alloy`.
This branch has genuine upstream ancestry, with the earlier `bee3b1e` revision as
a shallow history boundary. The original local snapshot is preserved on
`work/knowledge-evidence`.

Ganesh retains knowledge and UI ownership. Santosh retains the simulation and
investigation loop. Shared changes are limited to baseline input fairness, a
measurement guard before loop execution, CLI integration and audit presentation;
the shared Claim contract was not expanded.

Recent feature commits include `4535aae` (reviewed-evidence gates), `6d9d533`
(research UI), `d69cd19` (explicit reproduction settings), `f8afa39` (audit
provenance) and `6f08fc5` (audit download and malformed input handling).
Use `git rev-parse HEAD` for the final documentation revision.

No branch, push or PR was created: the authorized Work GitHub connection returned
HTTP 403, `Resource not accessible by integration`, on branch creation.
No remote merge or deployment was performed.

## Acceptance status

| Check | Verified now | Still open |
| --- | --- | --- |
| K1: Bond ingestion | Native search response normalized from three records to two works; exact-query cache replay made no network/model calls | Live standalone Codex app-server bridge |
| K2: real evidence | Three reviewed full-text sources with locations, settings and mismatch explanations; extraction rejection checks pass | A reviewed eligible cross-paper claim pair: current bundle has zero runnable claims |
| K3: comparison semantics | Unit checks cover multiple differences, missing/nonfinite settings, units, methods, systems and a mocked loop measurement guard | Four complete investigation scenarios require PySINDy |
| K4: method provenance | Supported-method, deduplication, citation and quotation checks pass; baseline preserves all claim fields | End-to-end online extraction and selection |
| K5: UI and exports | Streamlit AppTest covers reviewed-mode refusal, saved partial/resolved/unstated/insufficient results, failed-run clearing, downloads and history filters | Browser walkthrough and actual local notebook replay |
| K6: delivery | Focused commits on a real upstream branch, lint, documentation and an apply-checked patch | Locked install, complete simulations, published branch and CI |

The evidence bundle does not establish a real published contradiction. Its
`blockers` identify differences in noise construction, feature libraries,
method implementations and measured quantities. Do not relabel synthetic scenarios
as literature, or treat matching a simulated number as proof of an author's setting.
No new scientific finding or efficiency advantage has been demonstrated by this lane.

## Checks run here

The available environment is Python 3.11 with an existing shared package set,
Streamlit 1.30 and no PySINDy. It does not satisfy the project lockfile.

```bash
PYTHONPATH=src PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python \
  .venv/bin/python -m pytest -q --disable-warnings
.venv/bin/python -m ruff check .
git diff --check
```

- Full suite: **98 passed, 8 failed**, 14 warnings. All eight failures stem from
  missing PySINDy: four investigation scenarios, three adapter checks and one
  runner error-message assertion seeing the import error before method validation.
- Focused knowledge, UI, baseline, Bond, report and mocked-loop checks:
  **96 passed**, 14 warnings.
- Ruff and whitespace checks pass.
- `evidence-check` reports three sources, zero runnable claims and no eligible pair.
  `demo --evidence` refuses this bundle before running an investigation.
- Raw native Bond import and exact-query replay were exercised separately, with
  model and transport entry points replaced by raising sentinels during replay.

`uv sync --cache-dir /private/tmp/alloy-uv-cache` could not download dependencies:
DNS resolution failed for `files.pythonhosted.org`. A normal Streamlit launch
failed at socket bind with `PermissionError: Operation not permitted`; no browser
walkthrough or running server is claimed. The gods-plan controller also could not
create its protected state directory, so the approved work ran directly in this
session; no background worker is scheduled.

## Reproduce after dependencies are available

From the project root:

```bash
uv sync
uv run alloy evidence-check
uv run pytest -q
uv run ruff check .
uv run alloy demo
uv run alloy bench --alloy-only
uv run streamlit run ui/app.py
```

`demo` and `bench --alloy-only` use synthetic scenarios and local simulations.
They require no paid inference. `audit`, `demo --online` and a benchmark without
`--alloy-only` use Claude API inference; they were not run in this implementation.
The reviewed-evidence viewer requires no Bond credentials or Claude calls.

In the browser, inspect **Reviewed literature**, confirm that investigation is
disabled with explicit gaps, then load an exported investigation through
**Saved investigation**. Exercise partial results, failures, source links, history
filters and every available download. Run an offline synthetic investigation and
replay its exported notebook against its recorded run IDs.

## Next work, in order

1. Find a published data/script pair matching the supported experiment, or extend
   the adapter to one paper's exact published protocol. Record every implementation
   and metric difference before adding reviewed runnable claims. Two papers merely
   mentioning SINDy and noise are not enough.
2. Install the locked environment where dependency networking works. Run the full
   suite and bounded offline scenarios; diagnose any remaining code failures.
3. Complete the browser and notebook walkthrough above. Keep fixture-based UI
   checks separate from real simulation and scientific validation.
4. Apply or publish the patch through an authorized GitHub connection with working
   branch-write access, review CI and coordinate shared files before merging.

For this session, the portable patch is `/private/tmp/alloy-first-lane.patch`.
Apply it to the exact inspected upstream revision in a clean checkout:

```bash
git switch -c ganesh/knowledge-first-lane fec698ed0300ff142026f1ee90971ca0e7250da5
git apply --check /path/to/alloy-first-lane.patch
git apply /path/to/alloy-first-lane.patch
git diff --stat
```

The patch contains repository changes only; local tokens, `.env`, caches, run
outputs and the direct execution checkpoint are excluded. If upstream moved,
review overlap before applying rather than assuming this patch still applies.
