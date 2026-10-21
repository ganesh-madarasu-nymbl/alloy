"""Research package export: a notebook that reruns every experiment from its spec."""

import json
from pathlib import Path

import nbformat as nbf

from alloy.contracts import RunResult


def to_notebook(title: str, results: list[RunResult], path: Path) -> Path:
    specs = [r.spec.model_dump() for r in results]
    nb = nbf.v4.new_notebook()
    nb.cells = [
        nbf.v4.new_markdown_cell(f"# {title}\n\nRerun every experiment from its saved spec."),
        nbf.v4.new_code_cell(
            "from alloy.contracts import Budget, ExperimentSpec\n"
            "from alloy.experiments.runner import Runner\n\n"
            f"specs = {json.dumps(specs, indent=1, default=str)}\n"
            f"runner = Runner(Budget(runs={len(specs)}, minutes=30), 'runs/replay')\n"
            "results = [runner.run(ExperimentSpec(**s)) for s in specs]\n"
            "[(r.spec.method, r.spec.conditions.get('noise'), r.metrics) for r in results]"
        ),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(nb, path)
    return path
