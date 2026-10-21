"""Read saved results without executing experiments or trusting uploaded filesystem paths."""

from pathlib import Path

from alloy.agent.loop import Investigation


def read_investigation(data: bytes) -> Investigation:
    if len(data) > 5_000_000:
        raise ValueError("Investigation records must be smaller than 5 MB")
    inv = Investigation.model_validate_json(data)
    cases = inv.challenge.get("cases", [])
    if not isinstance(cases, list) or not all(isinstance(case, dict) for case in cases):
        raise ValueError("Unseen cases must be a list of recorded cases")
    return inv


def local_notebook(path: str | None, run_root: Path) -> bytes | None:
    if not path:
        return None
    candidate = Path(path).resolve()
    if candidate.suffix != ".ipynb" or not candidate.is_relative_to(run_root.resolve()):
        return None
    try:
        return candidate.read_bytes()
    except OSError:
        return None
