"""Dead-End Map: failed runs and losing combinations, kept with their conditions."""

import json
from datetime import UTC, datetime
from pathlib import Path

from alloy.contracts import RunResult


class DeadEndMap:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, result: RunResult, reason: str) -> None:
        entry = {
            "at": datetime.now(UTC).isoformat(),
            "run_id": result.id,
            "task": result.spec.task,
            "method": result.spec.method,
            "conditions": result.spec.conditions,
            "metrics": result.metrics,
            "error": result.error,
            "reason": reason,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line]

    def lookup(self, method: str, **conditions) -> list[dict]:
        return [
            e
            for e in self.entries()
            if e["method"] == method and all(e["conditions"].get(k) == v for k, v in conditions.items())
        ]
