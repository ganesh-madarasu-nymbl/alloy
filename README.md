# Alloy

Alloy audits answers about why published results disagree. An AI agent can find a likely cause in a handful of runs. Alloy checks that answer: it reruns each paper's setting, tests one condition at a time, compares methods on fixed seeds, tries cases neither paper covered, and writes a report a reviewer can rerun line by line. Ganesh and Santosh are building it for the OSI Hackathon Boston (October 2026), with the Valency Bond MCP as the literature source.

A researcher gives Alloy a goal, a supported simulator and a compute budget. Alloy returns an `audit.md` with:

- the claims, with the conflicts it set aside and why
- a reproduction of each paper's result
- the error each differing condition adds, or the unstated setting that reproduces the gap
- a controlled comparison with standard errors, and a warning when two methods are tied
- the winner's results on unseen cases
- a replay notebook and a log of what failed

`uv run alloy audit --scenario short_record` runs a plain Claude agent and compares its cause and method with Alloy's investigation, adding a "second opinion" table to the report. This command uses Claude API inference; `demo` and `bench --alloy-only` run offline.

## Why an auditor

We first set out to show that Alloy finds good method combinations with fewer experiments than a plain agent. Our own benchmark says no: on five scenarios, Claude Sonnet 5.5 found every cause in 4 to 14 runs, against Alloy's 17 to 45 (details below). Speed is not where Alloy helps. It helps with trust: the agent's answer comes from a few lucky seeds and its prior knowledge, while Alloy's comes with controlled evidence you can replay. In the short_record audit, both named the same method, and Alloy added that the runner-up sits within seed noise of it.

## Quick start

```bash
uv sync
uv run alloy demo            # offline: seed claims, no API calls
uv run pytest -q
uv run streamlit run ui/app.py
```

Offline mode reads synthetic claims in `data/seed/lorenz_claims.json` and runs locally.
Their placeholder quotations are not evidence of a published disagreement.

### Audit a collection under one budget

```bash
uv run alloy campaign --synthetic data/seed/collection_claims.json --plan-only
uv run alloy campaign --synthetic data/seed/collection_claims.json --runs 60 --minutes 5
uv run alloy campaign --evidence data/evidence/sindy_review.json --plan-only
```

The planner accepts at most 20 canonical works and 100 claims, screens every pair,
and queues up to three discrepancies with visible ranking reasons. One run/time
budget covers the entire queue. Failed simulations count; insufficient budgets
leave pairs deferred, and uncertain accounting stops further launches. The current
campaign supports Lorenz/PySINDy; coatings remains a separate command.

Choose **Collection campaign** in the UI to preview the queue and run it, or
**Saved campaign** to inspect an exported `campaign.json` without execution or
reading uploaded paths. Campaign exports embed child investigations; transfer raw
run folders separately for replay notebooks. Every conclusion applies to its own
pair. Three selected audits can remain partial under 60 total runs.

The implementation is committed locally; actual simulations, browser/replay checks
and publication remain blocked in this session. The reviewed bundle has zero
eligible pairs. See the [detailed implementation contract](docs/multi-paper-implementation.md)
and [current acceptance ledger](docs/multi-paper-handoff.md).

For Bond discovery using your existing Codex login, install the Valency plugin and complete
`codex mcp login valency`. Copy `.env.example` to `.env` (preserve any existing settings), then run:

```bash
uv run alloy bond-check
uv run alloy bond-search "sparse identification of nonlinear dynamics Lorenz noise" --limit 5
```

These two commands reuse Codex's OAuth storage through its installed app-server protocol.
They do not copy tokens or start a model turn. Discovery requires a local Codex version
supporting MCP tool calls through app-server. `bond-check` reports the available tools
and authentication/runtime status; a successful `bond-search` verifies a real tool call.
The search caches raw results and metadata/abstracts in `cache/`; abstracts are not full-text
evidence of a disagreement. Missing passages stay missing. Runtime, network and sign-in
failures exit with an error rather than substituting demo papers.

If a native MCP client already returned a search response, import that JSON directly:

```bash
uv run alloy bond-import /path/to/result.json --query "the exact original query" --limit 5
uv run alloy evidence-check
```

Use the original search query and limit so cached replay represents the original request.
Import retains the raw response and labels normalized passages as metadata/abstracts.
It needs no subprocess, model call or credentials copied into Alloy.

`data/evidence/sindy_review.json` contains three reviewed primary sources, source locations,
short excerpts, stated settings and explicit reproduction gaps. It currently contains **no
eligible cross-paper claim pair**: the papers differ from the adapter in noise construction,
feature library, method implementation or measured quantity. `alloy demo --evidence <bundle>`
validates the bundle and refuses to run when no eligible pair exists. It never substitutes
synthetic claims. Exact literature reproduction requires all adapter settings to be explicit;
the separate synthetic hidden-setting scenario explores assumptions rather than author facts.

In the UI, choose **Reviewed literature** to inspect those gaps, or **Saved investigation**
to upload a previously exported `runs/<id>/investigation.json`. Viewing saved results does
not run experiments. The result view includes skipped pairs, controlled changes, unstated
setting hypotheses, mean/worst/standard error, unseen cases, method provenance and filterable
failure history. Investigation JSON, graph and Markdown audit exports are available; replay notebooks require their local
run folder. See [the lane handoff](docs/first-lane-handoff.md) for verification limits.

For the full online investigation, also configure your Claude API access. With
`ALLOY_BOND_BACKEND=codex`, Bond discovery uses Codex OAuth; claim extraction, method selection
and the referee still use Claude API calls. The optional `ALLOY_BOND_BACKEND=claude` path
uses the hosted Claude MCP connector and requires its own server authorization.

```bash
uv run alloy check           # shows model and whether Bond is configured
uv run alloy demo --online --referee
```

To check a run replays exactly, execute its notebook:

```bash
uv run jupyter nbconvert --to notebook --execute runs/<id>/replay.ipynb --output executed.ipynb
```

On 21 Oct 2026 a demo run's 34 experiments replayed with identical metrics.

## The loop

| Stage | What runs | Code |
|---|---|---|
| 1 Search | Bond through Codex OAuth or the Claude MCP connector, cached to `cache/` | `knowledge/bond.py` |
| 2 Understand | Claim extraction and the evidence graph | `knowledge/extract.py`, `knowledge/graph.py` |
| 3 Investigate | Condition Check, then a rerun at each claim's conditions | `knowledge/conditions.py`, `agent/loop.py` |
| 4 Improve | Method search, then a controlled comparison | `knowledge/methods.py`, `experiments/compare.py` |
| 5 Verify | MirageLab: unseen start points and noise levels | `experiments/verify.py` |
| 6 Remember | Dead-End Map, replay notebook and audit report | `memory/deadend.py`, `experiments/export.py`, `experiments/report.py` |

`agent/loop.py` wires the stages together. `agent/referee.py` argues against the final verdict.

## First demo: equations from noisy data

The physics task recovers the Lorenz equations with PySINDy. The seed claims say plain SINDy recovers the equations at low noise and fails at high noise. Alloy reruns both, compares smoothing, ensembling and their combination under one budget, and checks the winner on three unseen cases.

The seed claims hold placeholder quotes. Keep them labeled as synthetic in a demo.
Reviewed literature must pass the evidence-bundle checks before it can replace this input;
retrieving a DOI or an abstract does not establish the reported number or its settings.

## Second task: radiative cooling coatings

`uv run alloy coatings --layers 3 --tolerance 30` compares three designs for a coating on a silver mirror: one SiO2 emitter, the best of 12 random TiO2/SiO2 stacks, and the same search scored under thickness errors. The adapter uses the transfer-matrix method (`tmm`) with approximate optical constants listed in `experiments/data/optics.py`. It omits silver's UV interband absorption, so it underestimates solar absorption. Swap in measured data before trusting a number.

First run (3 layers, 30 nm thickness error): the single 1 um SiO2 layer cools 47 W/m^2 and loses the race after 2 seeds. Both searched stacks cool about 85 W/m^2 out of an ideal 148 W/m^2, and they tie under thickness errors (0.422 vs 0.426 cooling error, standard error about 0.01). A 30 nm error on micron-thick layers changes little. A sharper test needs thinner, resonant layers.

## Benchmark: Alloy vs a plain agent

`uv run alloy bench` runs both systems on the scenarios in `data/scenarios/` with the same claims, simulator and 60-run budget. All scenarios are synthetic and say so in their files.

| Scenario | What makes it hard |
|---|---|
| noise_simple | Nothing: one condition differs |
| noise_with_decoys | Three conditions differ; only noise matters |
| short_record | Three conditions differ; only record length matters |
| hidden_threshold | Both papers state the same conditions; one used a threshold it never reported |
| many_papers | Ten claims; three conflicts are traps (different system, different units, unsupported method) |

An oracle measures every method on 10 seeds that neither system sees. Each system scores on three things: whether it names the right cause, whether its recommended method is within 10% (or 0.02) of the oracle's best, and how many runs it used. Add `--alloy-only` to skip the plain agent and its API calls.

Results on 21 Oct 2026. Alloy runs once per scenario because its offline run is deterministic. The plain agent ran 5 times per scenario on Claude Sonnet 5.5 (`--repeat 5`, about 284k input and 46k output tokens in total).

These are upstream historical results, not reruns of this branch. They predate the baseline
prompt correction that supplies every Claim field, including units, zero values and source
quotations. The units-trap comparison therefore needs reevaluation with equal information.
No updated efficiency or superiority claim is established here; paid reruns were not performed.

| Scenario | Alloy cause / answer / runs | Plain agent (Sonnet 5.5, n=5) cause / answer / mean runs |
|---|---|---|
| noise_simple | 1/1 / 1/1 / 34 | 5/5 / 5/5 / 4.0 |
| noise_with_decoys | 1/1 / 1/1 / 43 | 5/5 / 5/5 / 4.4 |
| short_record | 1/1 / 1/1 / 45 | 5/5 / 5/5 / 13.8 |
| hidden_threshold | 1/1 / no method question / 17 | 5/5 / no method question / 12.4 |
| many_papers | 1/1 / 0/1, flagged as a tie / 41 | 5/5 / 0/5 / 7.4 |

An earlier single-run pass with Claude Opus 5.5 as the plain agent used 17 to 35 runs per scenario and once took the units trap in many_papers. Sonnet 5.5 never took the trap in 5 runs.

What the numbers say:

- The plain agent matches Alloy on every cause and every answer, and uses 3 to 10 times fewer runs.
- In noise_simple and noise_with_decoys, Sonnet named noise after about 4 runs without testing the decoy conditions. Its prior knowledge that noise breaks SINDy solves these scenarios. They test textbook knowledge more than investigation.
- Both systems miss the many_papers answer the same way. Alloy now races methods: it drops a method once it trails the leader by more than two combined standard errors and adds seeds to the rest, up to 9. After 9 seeds smoothed-sindy still leads (0.052 vs 0.066), so Alloy's verdict calls the two tied. The plain agent picks one without a warning.
- On these scenarios the data do not support the claim that Alloy finds good combinations with fewer experiments.

What would test the claim properly:

- Scenarios where the cause runs against textbook intuition, so prior knowledge misleads the agent.
- Real papers from Bond, where conditions sit in prose and many claims do not line up.
- An adaptive Alloy comparison that stops testing clear losers early and adds seeds only when two methods are close.

## Contracts

Both lanes build against `src/alloy/contracts.py`. The knowledge code writes `Claim` and `ExperimentSpec`. The experiment code reads specs and writes `RunResult`. Agree on any change to that file before you push it.

## Who owns what

| Area | Owner |
|---|---|
| `knowledge/` (Bond, claims, graph, Condition Check, method search), `ui/` | Ganesh |
| `experiments/` (adapters, runner, comparison, MirageLab, export), `agent/` | Santosh |
| `contracts.py`, `agent/baseline.py`, the demo | Both |

## Open work

- [x] Native-session Bond search, raw-result ingestion, deduplication and cache replay
- [ ] Verify the standalone Codex app-server bridge with a live Bond search
- [ ] Find a reviewed eligible real-paper pair; preserve source/adapter mismatch evidence
- [x] Baseline prompt includes every Claim field; historical results still need fair reruns
- [x] `experiments/adapters/tmm_adapter.py`: cooling coatings (stretch)
- [x] UI: condition differences, citation trail, saved records and failure history
- [x] Bounded collection planner, shared-budget campaign records and saved campaign UI
- [ ] Locked dependency install, complete simulation checks and browser walkthrough
- [ ] Publish Ganesh's local integration branch through the authorized Work connection
- [ ] Record the backup demo video from cached runs

## Adding a scientific task

Write an adapter with `name`, `task`, `methods`, `condition_keys` and `run(spec) -> (metrics, artifacts)`, call `register()`, and import it in `experiments/adapters/base.py`. Name lower-is-better metrics with an `_error` suffix.
