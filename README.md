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

Offline mode reads `data/seed/lorenz_claims.json` and runs everything locally in a few seconds.

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

For the full online investigation, also configure your Claude API access. With
`ALLOY_BOND_BACKEND=codex`, Bond discovery uses Codex OAuth; claim extraction, method selection
and the referee still use Claude API calls. The optional `ALLOY_BOND_BACKEND=claude` path
uses the hosted Claude MCP connector and requires its own server authorization.

```bash
uv run alloy check           # shows model and whether Bond is configured
uv run alloy demo --online --referee
```

## The loop

| Stage | What runs | Code |
|---|---|---|
| 1 Search | Bond through Codex OAuth or the Claude MCP connector, cached to `cache/` | `knowledge/bond.py` |
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

`uv run alloy bench` runs both systems on the scenarios in `data/scenarios/` with the same claims, simulator and 60-run budget. All scenarios are synthetic and say so in their files.

| Scenario | What makes it hard |
|---|---|
| noise_simple | Nothing: one condition differs |
| noise_with_decoys | Three conditions differ; only noise matters |
| short_record | Three conditions differ; only record length matters |
| hidden_threshold | Both papers state the same conditions; one used a threshold it never reported |
| many_papers | Ten claims; three conflicts are traps (different system, different units, unsupported method) |

An oracle measures every method on 10 seeds that neither system sees. Each system scores on three things: whether it names the right cause, whether its recommended method is within 10% (or 0.02) of the oracle's best, and how many runs it used. Add `--alloy-only` to skip the plain agent and its API calls.

Results on 21 Oct 2026 (plain agent: Claude Opus 5.5 at medium effort, one run per scenario unless noted):

| Scenario | Alloy cause / answer / runs | Plain agent cause / answer / runs |
|---|---|---|
| noise_simple | correct / correct / 32 | correct / correct / 31 |
| noise_with_decoys | correct / correct / 41 | correct / correct / 20 |
| short_record | correct / correct / 41 | correct / correct / 28 |
| hidden_threshold | correct / no method question / 17 | correct / no method question / 28 |
| many_papers (3 agent runs) | correct / missed / 36 | correct in 2 of 3 / missed in 3 of 3 / 17 to 24 |

What the numbers say:

- On small, clean tasks the plain agent matches Alloy and uses fewer runs.
- Alloy found the unstated threshold in 17 runs; the plain agent needed 28.
- In one of three many_papers runs, the plain agent chased the units trap (0.02 relative vs 2.0 percent) and blamed the time step. Alloy's Condition Check rules that pair out before running anything.
- Both systems miss the many_papers answer the same way. On seeds 0 to 4, smoothed-sindy beats smoothed-ensemble-sindy (0.042 vs 0.075); on the oracle's seeds the order flips (0.083 vs 0.058). Five seeds cannot separate them. Alloy reports a tie when two methods fall within each other's standard error, but here they do not on its own seeds.

Next: run each scenario several times for both systems, scale many_papers to real Bond output, and replace the fixed 5-seed comparison with an adaptive one.

## Contracts

Both lanes build against `src/alloy/contracts.py`. The knowledge code writes `Claim` and `ExperimentSpec`. The experiment code reads specs and writes `RunResult`. Agree on any change to that file before you push it.

## Who owns what

| Area | Owner |
|---|---|
| `knowledge/` (Bond, claims, graph, Condition Check, method search), `ui/` | Ganesh |
| `experiments/` (adapters, runner, comparison, MirageLab, export), `agent/` | Santosh |
| `contracts.py`, `agent/baseline.py`, the demo | Both |

## Open work

- [ ] Verify the installed Codex OAuth bridge with a live Bond search and cache the result
- [ ] Replace the seed placeholders with real Bond claims
- [ ] `agent/baseline.py`: plain agent with the same tools and budget, for the experiments-saved count
- [ ] `experiments/adapters/tmm_adapter.py`: cooling coatings (stretch)
- [ ] UI: condition diff view and the citation trail
- [ ] Record the backup demo video from cached runs

## Adding a scientific task

Write an adapter with `name`, `task`, `methods`, `condition_keys` and `run(spec) -> (metrics, artifacts)`, call `register()`, and import it in `experiments/adapters/base.py`. Name lower-is-better metrics with an `_error` suffix.
