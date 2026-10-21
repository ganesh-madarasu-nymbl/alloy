# Alloy

Alloy audits answers about why published results disagree. An AI agent can find a likely cause in a handful of runs. Alloy checks that answer: it reruns each paper's setting, tests one condition at a time, compares methods on fixed seeds, tries cases neither paper covered, and writes a report a reviewer can rerun line by line. Ganesh and Santosh are building it for the OSI Hackathon Boston (October 2026), with the Valency Bond MCP as the literature source.

A researcher gives Alloy a goal, a supported simulator and a compute budget. Alloy returns an `audit.md` with:

- the claims, with the conflicts it set aside and why
- a reproduction of each paper's result
- the error each differing condition adds, or the unstated setting that reproduces the gap
- a controlled comparison with standard errors, and a warning when two methods are tied
- the winner's results on unseen cases
- a replay notebook and a log of what failed

`uv run alloy audit --scenario short_record` runs a plain Claude agent first, then has Alloy check its cause and method and adds a "second opinion" table to the report.

## Why an auditor

We first set out to show that Alloy finds good method combinations with fewer experiments than a plain agent. Our own benchmark says no: on five scenarios, Claude Sonnet 5.5 found every cause in 4 to 14 runs, against Alloy's 17 to 41 (details below). Speed is not where Alloy helps. It helps with trust: the agent's answer comes from a few lucky seeds and its prior knowledge, while Alloy's comes with controlled evidence you can replay. In the short_record audit, both named the same method, and Alloy added that the runner-up sits within seed noise of it.

## Quick start

```bash
uv sync
uv run alloy demo            # offline: seed claims, no API calls
uv run pytest -q
uv run streamlit run ui/app.py
```

Offline mode reads `data/seed/lorenz_claims.json` and runs everything locally in a few seconds. For online mode, copy `.env.example` to `.env`, add the Valency MCP URL and token from the #valency setup guide, then run:

```bash
uv run alloy check           # shows model and whether Bond is configured
uv run alloy demo --online --referee
```

## The loop

| Stage | What runs | Code |
|---|---|---|
| 1 Search | Bond search through the Claude MCP connector, cached to `cache/` | `knowledge/bond.py` |
| 2 Understand | Claim extraction and the evidence graph | `knowledge/extract.py`, `knowledge/graph.py` |
| 3 Investigate | Condition Check, then a rerun at each claim's conditions | `knowledge/conditions.py`, `agent/loop.py` |
| 4 Improve | Method search, then a controlled comparison | `knowledge/methods.py`, `experiments/compare.py` |
| 5 Verify | MirageLab: unseen start points and noise levels | `experiments/verify.py` |
| 6 Remember | Dead-End Map, replay notebook and audit report | `memory/deadend.py`, `experiments/export.py`, `experiments/report.py` |

`agent/loop.py` wires the stages together. `agent/referee.py` argues against the final verdict.

## First demo: equations from noisy data

The physics task recovers the Lorenz equations with PySINDy. The seed claims say plain SINDy recovers the equations at low noise and fails at high noise. Alloy reruns both, compares smoothing, ensembling and their combination under one budget, and checks the winner on three unseen cases.

The seed claims hold placeholder quotes. Replace them with real Bond results before the demo, and check that the two DOIs say what the seed file says they do.

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

| Scenario | Alloy cause / answer / runs | Plain agent (Sonnet 5.5, n=5) cause / answer / mean runs |
|---|---|---|
| noise_simple | 1/1 / 1/1 / 32 | 5/5 / 5/5 / 4.0 |
| noise_with_decoys | 1/1 / 1/1 / 41 | 5/5 / 5/5 / 4.4 |
| short_record | 1/1 / 1/1 / 41 | 5/5 / 5/5 / 13.8 |
| hidden_threshold | 1/1 / no method question / 17 | 5/5 / no method question / 12.4 |
| many_papers | 1/1 / 0/1 / 36 | 5/5 / 0/5 / 7.4 |

An earlier single-run pass with Claude Opus 5.5 as the plain agent used 17 to 35 runs per scenario and once took the units trap in many_papers. Sonnet 5.5 never took the trap in 5 runs.

What the numbers say:

- The plain agent matches Alloy on every cause and every answer, and uses 3 to 10 times fewer runs.
- In noise_simple and noise_with_decoys, Sonnet named noise after about 4 runs without testing the decoy conditions. Its prior knowledge that noise breaks SINDy solves these scenarios. They test textbook knowledge more than investigation.
- Both systems miss the many_papers answer the same way, because 5 seeds cannot separate smoothed-sindy from smoothed-ensemble-sindy.
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

- [ ] Get the Valency MCP URL and token, run the first Bond search, and cache the result
- [ ] Replace the seed placeholders with real Bond claims
- [ ] `agent/baseline.py`: plain agent with the same tools and budget, for the experiments-saved count
- [ ] `experiments/adapters/tmm_adapter.py`: cooling coatings (stretch)
- [ ] UI: condition diff view and the citation trail
- [ ] Record the backup demo video from cached runs

## Adding a scientific task

Write an adapter with `name`, `task`, `methods`, `condition_keys` and `run(spec) -> (metrics, artifacts)`, call `register()`, and import it in `experiments/adapters/base.py`. Name lower-is-better metrics with an `_error` suffix.
