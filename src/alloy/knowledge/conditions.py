"""Condition Check: are two conflicting claims comparable, and which condition differs?"""

from dataclasses import dataclass, field
from math import isfinite
from typing import Any

from alloy.contracts import Claim


@dataclass
class ConditionReport:
    a: str
    b: str
    comparable: bool
    shared: dict[str, Any] = field(default_factory=dict)
    differing: dict[str, tuple[Any, Any]] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)  # stated by one claim only
    reproducible: list[str] = field(default_factory=list)  # differing keys an adapter can vary
    notes: list[str] = field(default_factory=list)


def check(a: Claim, b: Claim, adapter_keys: tuple[str, ...] = ()) -> ConditionReport:
    report = ConditionReport(a=a.id, b=b.id, comparable=True)
    if a.quantity != b.quantity:
        report.comparable = False
        report.notes.append(f"different quantities: {a.quantity} vs {b.quantity}")
    if a.unit != b.unit:
        report.comparable = False
        report.notes.append(f"different units: {a.unit} vs {b.unit}")
    if a.method != b.method:
        report.comparable = False
        report.notes.append("methods differ; changing conditions alone cannot isolate the cause")
    if (a.value is not None or b.value is not None) and (not a.unit or not b.unit):
        report.comparable = False
        report.notes.append("numeric claims need explicit units (including dimensionless)")

    for key in sorted(set(a.conditions) | set(b.conditions)):
        values = (a.conditions.get(key), b.conditions.get(key))
        if any(v is None or v == "" or (isinstance(v, float) and not isfinite(v)) for v in values):
            report.missing.append(key)
        elif key in a.conditions and key in b.conditions:
            va, vb = a.conditions[key], b.conditions[key]
            if va == vb:
                report.shared[key] = va
            else:
                report.differing[key] = (va, vb)
        else:
            report.missing.append(key)

    if not a.conditions.get("system") or not b.conditions.get("system"):
        if "system" not in report.missing:
            report.missing.append("system")
    if "system" in report.differing:
        report.comparable = False
        report.notes.append("claims study different systems")
    if report.missing:
        report.comparable = False
        report.notes.append("insufficient evidence: unstated conditions: " + ", ".join(report.missing))
    if len(report.differing) > 1:
        report.comparable = False
        report.notes.append("multiple conditions differ; a controlled multi-variable study is required")
    report.reproducible = [k for k in report.differing if k in adapter_keys]
    if report.differing:
        report.notes.append("condition differences are hypotheses, not proof of the cause")
    if report.comparable and not report.differing:
        report.notes.append("no stated condition explains the gap; check unstated settings")
    return report
