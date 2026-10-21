"""Adapters wrap one scientific tool behind a single call: spec in, metrics out."""

from typing import Any, Protocol

from alloy.contracts import ExperimentSpec


class Adapter(Protocol):
    name: str
    task: str
    methods: tuple[str, ...]
    # Conditions the adapter understands, so Condition Check knows what it can reproduce.
    condition_keys: tuple[str, ...]
    # Candidate values per condition, used to search for settings a paper never states.
    sweeps: dict[str, list[Any]]

    def run(self, spec: ExperimentSpec) -> tuple[dict[str, float], dict[str, Any]]:
        """Return (metrics, artifacts). Lower-is-better metrics should end in `_error`."""
        ...


_REGISTRY: dict[str, Adapter] = {}


def register(adapter: Adapter) -> Adapter:
    _REGISTRY[adapter.name] = adapter
    return adapter


def get_adapter(name: str) -> Adapter:
    if name not in _REGISTRY:  # adapters register on import
        from alloy.experiments.adapters import pysindy_adapter, tmm_adapter  # noqa: F401
    try:
        return _REGISTRY[name]
    except KeyError:
        raise KeyError(f"unknown adapter {name!r}; registered: {sorted(_REGISTRY)}") from None
