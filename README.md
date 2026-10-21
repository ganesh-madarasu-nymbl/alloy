# Alloy

Alloy finds published results that disagree, reruns them to find the condition behind the gap, and tests whether combining existing methods beats each one. Ganesh and Santosh are building it for the OSI Hackathon Boston (October 2026), with the Valency Bond MCP as the literature source.

A researcher gives Alloy a goal, a supported simulator and a compute budget. Alloy returns:

- why the papers disagree, with the claims and conditions side by side
- a reproduction of the gap
- a controlled comparison of candidate methods under one budget
- a check of the winner on cases it never saw
- a notebook that reruns every experiment, plus a log of what failed

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
| 6 Remember | Dead-End Map and the replay notebook | `memory/deadend.py`, `experiments/export.py` |

`agent/loop.py` wires the stages together. `agent/referee.py` argues against the final verdict.

## First demo: equations from noisy data

The physics task recovers the Lorenz equations with PySINDy. The seed claims say plain SINDy recovers the equations at low noise and fails at high noise. Alloy reruns both, compares smoothing, ensembling and their combination under one budget, and checks the winner on three unseen cases.

The seed claims hold placeholder quotes. Replace them with real Bond results before the demo, and check that the two DOIs say what the seed file says they do.

## Benchmark: Alloy vs a plain agent

`uv run alloy bench` runs both systems on the scenarios in `data/scenarios/` with the same claims, simulator and 60-run budget. The scenarios are synthetic. In two of them several conditions differ between the papers and only one causes the failure. An oracle measures every method on 10 seeds that neither system sees. Each system scores on three things: whether it names the right cause, whether its recommended method is within 10% of the oracle's best, and how many runs it used. Add `--alloy-only` to skip the plain agent and its API calls.

First results (21 Oct 2026, Claude Opus 5.5 at medium effort for the plain agent):

| Scenario | System | Cause | Answer | Runs |
|---|---|---|---|---|
| noise_simple | Alloy | correct | correct | 32 |
| noise_simple | plain agent | correct | correct | 35 |
| noise_with_decoys | Alloy | correct | correct | 41 |
| noise_with_decoys | plain agent | correct | correct | 19 |
| short_record | Alloy | correct | correct | 41 |
| short_record | plain agent | correct | correct | 34 |

The two systems tie on accuracy, and the plain agent used fewer runs in two of three scenarios. On tasks this small, Alloy does not yet save experiments. Next steps: an adaptive comparison in place of fixed seeds, harder scenarios (interacting causes, causes the papers never state), and real Bond papers in place of pre-extracted claims.

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
