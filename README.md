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
