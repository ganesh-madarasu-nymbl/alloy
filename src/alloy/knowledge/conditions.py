"""Condition Check: are two conflicting claims comparable, and which condition differs?"""

from dataclasses import dataclass, field
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
    if a.unit and b.unit and a.unit != b.unit:
        report.comparable = False
        report.notes.append(f"different units: {a.unit} vs {b.unit}")

    for key in sorted(set(a.conditions) | set(b.conditions)):
        if key in a.conditions and key in b.conditions:
            va, vb = a.conditions[key], b.conditions[key]
            if va == vb:
                report.shared[key] = va
            else:
                report.differing[key] = (va, vb)
        else:
            report.missing.append(key)

    if report.shared.get("system") is None and "system" in report.differing:
        report.comparable = False
        report.notes.append("claims study different systems")
    report.reproducible = [k for k in report.differing if k in adapter_keys]
    if report.comparable and not report.differing:
        report.notes.append("no stated condition explains the gap; check unstated settings")
    return report
