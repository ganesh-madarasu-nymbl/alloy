# Finish Ganesh's first lane: knowledge and research UI

Plan prepared on October 21, 2026. Status: planned; the implementation waves below have not been executed.

## Outcome

A researcher can inspect real source evidence, understand why two results may differ, see which experiments Alloy can actually run, and follow each recommendation through Santosh's experiment results back to its sources.

Keep the artifact's ownership split: Ganesh owns stages 1 and 2, method discovery in stage 4, Condition Check, and the UI. Santosh owns the investigation loop, simulations, comparison, unseen-case verification and replay export. Contracts, benchmark fairness and integration are shared. The artifact also assigns Ganesh the Dead-End Map view/storage; reuse the storage Santosh has already built.

This is a bounded hackathon POC under gods-plan. Scientific feasibility remains an experiment; provenance, compatibility and visible failure behavior are required. A negative result can be useful. A new discovery or a winning combination is not an acceptance requirement.

## Starting evidence

- Local branch: `work/knowledge-evidence`, head `4428e5d`. Our three feature/fix commits cover evidence validation and UI, the Codex Bond bridge, and duplicate-paper removal.
- Our local base is a reconstructed snapshot of upstream through `01a7e65`, not a normal checkout with the real upstream ancestry. No remote is configured. Our commits have not been pushed.
- Current GitHub head inspected: `bee3b1e9bc424fe58cd5ab5620703a2bd6fed092`. Santosh added condition attribution, hidden-setting search, incomparable-pair skipping, richer method comparisons, five synthetic scenarios and repeated benchmark runs.
- Native Valency search succeeded in this session. Three index records normalized to two distinct works, and cached replay succeeded. This verifies discovery and cache ingestion, not full-text evidence or the complete online investigation.
- The standalone Codex app-server bridge is implemented but its live operation remains unverified after a startup denial. Keep this distinct from native session access.
- Local knowledge verification last recorded: 32 focused tests and Ruff passed. Full simulation was unavailable in the local environment. Upstream CI is separate evidence and does not cover our unpushed changes.
- Published seed claims still contain placeholder passages. The method search is partly a fixed offline list; its online citations need validation. Our old single-variable comparison restriction conflicts with the new loop's multi-condition investigations.

Source references: [original ownership artifact](https://claude.ai/artifact/QU2T7xFDniC8czxjKbc7DD?sk=gPm492abre6cLhkSGyevQw), [upstream revision](https://github.com/santoshnymbl/alloy/tree/bee3b1e9bc424fe58cd5ab5620703a2bd6fed092), and local `docs/knowledge-slice.md` for the earlier slice's verification limits. This plan replaces that slice's single-variable-only restriction when the new loop is integrated; it does not retroactively change its results.

## Acceptance scenarios

| ID | Required behavior | Evidence at completion |
| --- | --- | --- |
| K1 | Given Bond records with duplicate index entries, discovery preserves raw provenance and presents each work once. Cached replay makes no network or model calls. | Live-response normalization fixture and offline replay check. |
| K2 | Given a scientific claim, its paper, exact supplied passage, location, metric, units and stated settings can be inspected. Unknown settings stay unknown; abstracts and demo claims are visibly distinguished from reviewed full text. | Reviewed evidence bundle from at least two distinct papers; rejection checks for fabricated quotations and unsupported numeric values. |
| K3 | Given a candidate pair, Alloy distinguishes incompatible evidence, an investigable condition difference and insufficient evidence. Multiple stated differences remain available to the newer loop; unstated settings are hypotheses with explicit assumptions. | Compatibility tests plus the loop's existing single-condition, decoy-condition and hidden-setting scenarios. |
| K4 | Given a weakness and supported adapter methods, every proposed method is supported, unique and tied to a retrieved source or explicitly labeled as an engineering hypothesis. | Candidate validation checks, including fabricated citations and unsupported methods. |
| K5 | Given a completed or partial investigation, the UI shows sources, condition differences, skipped pairs, attribution, method comparisons, uncertainty, unseen checks, failures and exports without inventing success. | Streamlit behavior checks and manual interaction with representative saved/live local results. |
| K6 | Given the integrated lane on a genuine upstream branch, another developer can install the project, run the documented checks and replay the demonstration without paid services. | Branch/diff review, lint/tests, documented demo and portable evidence/result bundle. |

Real-literature acceptance requires a reviewed eligible pair: distinct works, the same supported method and measured quantity, interpretable units and enough stated settings to define the experiment. Differences across conditions are not automatically contradictory claims. If the source search does not produce this pair, record the gap and leave that acceptance item open; do not relabel synthetic claims as literature.

## Wave 0 — Establish one compatible base

**Goal:** integrate existing work without losing either lane's progress.

1. Preserve our three changes as patches and keep the current branch intact.
2. Refresh GitHub head and obtain a proper checkout with genuine upstream history. Use the authorized `ganesh-madarasu-nymbl` connection. If branch/push access remains unavailable, keep a reviewable patch bundle and report delivery as local; never upload reconstructed history to `main`.
3. Apply our changes selectively to a new integration branch. Preserve Santosh's CLI benchmark flags, method fallback, attribution fields, expanded verdict states and multi-condition loop.
4. Resolve condition-check semantics in wave 2 rather than restoring the obsolete blanket rejection of multiple differences.
5. Establish the locked project environment with `uv sync`. Record any dependency/network failures separately from code failures.
6. Audit affected callers: CLI, loop, UI, extraction, candidate selection and the benchmark. Adopt Santosh's current contracts; propose any additional contract changes explicitly before implementing them.

**Exit:** a reviewed combined diff against a real upstream revision, or an explicitly local integration snapshot with publication blocked. Offline knowledge and existing loop checks pass wherever dependencies permit. No feature is counted as delivered merely because its patch exists.

**Commit:** `chore(integration): align knowledge lane with latest investigation loop`.

## Wave 1 — Replace placeholder evidence

**Goal:** make the literature input credible and replayable.

1. Reuse the verified native Bond search and normalization. Add a documented raw-result import/cache path so the demo is not dependent on the blocked standalone process bridge. Keep transport and evidence status visible; never silently fall back to synthetic results.
2. Search narrowly around SINDy, Lorenz, measurement noise, smoothing and ensembles. Follow references to find an eligible pair, not simply two papers that mention noise.
3. Review accessible original paper passages, figures or tables. Record paper identity, source URL, section/page/table, evidence type and review status in a versioned sidecar bundle keyed to claim IDs. Keep the shared `Claim` contract unchanged unless both lanes agree it must expand.
4. Build a small manually checked claim set from at least two distinct papers. An abstract is discovery evidence; detailed experiment settings need the relevant source text. Separate stated values, unknown values and assumptions used in a reproduction.
5. Retain and strengthen quote validation. Quote occurrence alone does not verify that the metric, units, numeric value and conditions were extracted correctly; check those against the source too.
6. Keep synthetic scenarios available under an explicit demo label. Package redistributable evidence excerpts and metadata rather than committing whole papers without a reason.

**Exit:** K1 and K2 pass, including a human-reviewed eligible pair. If none is found, retain the useful source bundle and report the unresolved scientific input instead of manufacturing a disagreement.

**Commit:** `feat(knowledge): add reviewed literature evidence and cached ingestion`.

## Wave 2 — Make the evidence graph and Condition Check investigation-ready

**Goal:** send Santosh a scientifically interpretable experiment question.

1. Preserve stable paper/claim IDs, source references and the paper → claim → method/condition trail. Treat graph conflicts as candidate discrepancies, not proven contradictions.
2. Validate quantities, explicit units, systems, supported methods and finite values. Missing numeric units or required settings must not silently become defaults. Apply only explicit, tested unit conversions; otherwise explain why comparison is blocked.
3. Keep same-method condition investigations separate from comparisons between candidate methods.
4. Allow multiple stated conditions to differ when the adapter supports them. Return all differences so the new loop can reproduce the pair and vary conditions. Do not present one-at-a-time attribution as proof that interactions are absent.
5. Handle missing settings by distinguishing unknown source values from explicitly chosen simulation assumptions. Permit the new hidden-setting search under those assumptions, with its existing `likely_unstated_cause` result; do not turn a search match into a verified author setting.
6. Return concrete skip or insufficient-evidence reasons. Preserve the new loop's incompatible-system, unit and unsupported-method trap handling.

**Exit:** K3 passes across single differences, multiple differences, no stated differences, missing values, incompatible units/systems and unsupported methods. Existing hidden-setting and decoy scenarios still work. The UI can explain every rejection.

**Commit:** `feat(knowledge): classify evidence gaps and investigable condition differences`.

## Wave 3 — Make recommendations traceable to literature

**Goal:** propose a small, defensible set of runnable improvements.

1. Use the investigated weakness to query Bond and inspect relevant source passages or citations.
2. Validate each candidate's cited paper against the retrieved set, validate its rationale against the supplied evidence, deduplicate candidates and restrict execution to the adapter's supported methods.
3. Preserve Santosh's fallback for weaknesses absent from the offline prior. Label such candidates as untested engineering hypotheses rather than sourced scientific findings.
4. Distinguish a published method from a proposed combination. Evidence for smoothing and evidence for ensembles do not prove that their combination improves results.
5. Hand candidates to the existing comparison runner. Record rationale and source IDs; leave simulation, ranking and unseen verification in Santosh's lane.

**Exit:** K4 passes. An invented citation cannot appear as verified support, an unsupported method cannot reach execution, and a losing combination remains a valid result.

**Commit:** `feat(knowledge): validate literature-backed method candidates`.

## Wave 4 — Finish the research UI and failure history

**Goal:** let a researcher and a judge understand the complete evidence trail.

1. Keep the goal, supported task and run/time budget controls. Provide clearly labeled cached-evidence and synthetic demonstration paths. Service-dependent actions must be explicit.
2. Show paper links, quoted evidence with location/type, metrics and units, review status and condition differences side by side.
3. Show selected and skipped pairs, the gap being investigated, measured attribution and any searched-but-unstated setting. Use language consistent with the verdict's uncertainty.
4. Preserve Santosh's latest comparison table: method rows, mean/worst error and uncertainty where available. Add method rationale/source links and distinguish proposed combinations. Do not reuse our old chart layout that interprets result fields as methods.
5. Show unseen-case results and how they support or weaken the recommendation. Display failed runs, budget exhaustion, ties and insufficient evidence as meaningful outcomes.
6. Reuse `DeadEndMap` storage; add a filterable view of method, conditions, measured result and failure reason. A failed attempt under one setting is not a universal claim that a method fails.
7. Expose the investigation JSON, evidence graph/bundle and replay notebook. Support viewing saved results so a UI rerun does not rerun experiments or trigger paid inference.

**Exit:** K5 passes for success, likely unstated cause, insufficient evidence, skipped pairs, failed runs and exhausted budget. Evidence links and downloads are manually exercised. The cached presentation works without service access.

**Commit:** `feat(ui): show research evidence investigation results and failed attempts`.

## Wave 5 — Integrate, verify and hand off

**Goal:** finish our lane as a reproducible contribution Santosh can use.

1. Refresh upstream once more, review overlapping changes and rerun the relevant checks on the combined revision.
2. Run `uv run ruff check .`, `uv run pytest -q`, focused UI behavior checks and a bounded offline investigation. Run the existing representative synthetic scenarios without the paid plain-agent path; keep their label explicit.
3. Run the reviewed real-evidence example through the supported local adapter. Track source parameters versus reproduction assumptions and retain negative or inconclusive findings.
4. Check the replay notebook and exports against the recorded run IDs and evidence. Manually exercise the goal/budget form, result views, saved result loading and downloads. Passing tests alone does not finish UI acceptance.
5. Fix the shared benchmark input omission before using its units-trap result: the plain agent currently receives claim text without units. Verify equivalent claim information, simulator capabilities and budget. Santosh's new `--repeat` support is already present; do not rebuild it. Paid repeated benchmark runs remain outside this plan's execution permission.
6. Update README/open work, replace stale single-variable-only guidance, document service access limitations and write a short handoff listing the integration revision, evidence bundle, check results and remaining scientific uncertainty.
7. Keep commits focused at each wave. Publish the integration branch through the authorized Work account when push access is verified. Record local, pushed, CI-passed and integrated states separately; leave merging and deployment outside this plan.

**Exit:** all K1–K6 acceptance evidence is recorded; any blocked check remains visibly open. Our branch/patch is reviewable and Santosh can consume the knowledge outputs without changing his simulator design. No claim of discovery, speedup or scientific superiority exceeds the measured evidence.

**Commit:** `test(integration): verify knowledge lane and document reproducible handoff`.

## Dependencies and scope controls

- Sequence: wave 0 → wave 1 → wave 2 → wave 3 → wave 4 → wave 5. Saved synthetic UI fixtures can help build wave 4 earlier, but do not satisfy real-evidence acceptance.
- Existing authorization covers planning, reversible local implementation, checks and focused commits within this lane. This request prepares the plan; it does not launch an unattended worker or claim that implementation has begun.
- For substantial unattended or context-crossing execution, translate these waves and acceptance checks into the installed gods-plan controller's validated contract and reuse existing authorization. Keep one lead and one authoritative task state. Do not launch a second controller from a worker.
- No paid model/API fallback, credit purchases, merge, deployment, or new external communication is included. Cached replay and local simulation require no paid inference.
- Shared contract additions and changes to Santosh-owned modules must be explicit integration changes with affected callers checked. Reuse his implementations rather than duplicating them.
- First cuts if time runs short: coatings, interactive graph rendering, standalone transport debugging once cached import works, and visual polish. Preserve reviewed evidence, honest comparison semantics, unseen-result visibility and replay.
- Remaining risks: source papers may not supply an eligible pair; defaults may differ from the papers; unknown settings may be non-identifiable; an apparent combination gain may disappear on unseen cases; environment or GitHub access may block verification/publication. Record these as specific unresolved items, not as successful acceptance.
