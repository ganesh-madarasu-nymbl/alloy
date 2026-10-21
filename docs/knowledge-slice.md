# Knowledge evidence slice

Build on Santosh's scaffold (source commit `8cf25d0f23ee0e9be32cf75324222f44a23ad1a0`, updated with `01a7e65c84f546b465b86d3db7ca816ed56be7f0`).
This bounded prototype uses the existing contracts and does not change experiment ownership.

Acceptance:
- Missing or incompatible recorded comparison conditions block the current controlled comparison.
- The current single-variable runner only receives pairs with one varying condition.
- Extracted quotes must occur in the supplied passages; missing passages fail before an API call.
- The UI shows source provenance, placeholder warnings and a readable condition difference.
- Offline knowledge tests and Streamlit behavior checks run without API calls.

Scope: knowledge modules, UI and their tests. No contract changes, paid calls, merge or deployment.
Published claims and live Bond remain unverified until retrieved and reviewed against source papers.

## Verification

21 focused tests pass (`tests/test_knowledge.py`, `tests/test_evidence.py`), including
Streamlit AppTest for the starting evidence and populated result views. Ruff passes
for all changed Python files. Extraction calls are mocked; no paid API calls were made.

The local check used Python 3.11, Pydantic 2.13.4 and Streamlit 1.30 through an existing
system environment, not a fresh lockfile install. Full simulation is unverified here:
PySINDy is unavailable and the installed Anthropic SDK lacks `beta_tool`, which the
new upstream baseline imports. Run `uv sync`, `uv run pytest -q`, and `uv run ruff check .`
in the project environment before merging.

This increment validates quote occurrence in supplied passages, not the truth of the
claim or whether a Bond passage is verbatim full text. Demo seeds remain placeholders.
A one-variable comparison is a testable hypothesis, not proof of a scientific cause.
