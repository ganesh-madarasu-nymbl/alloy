"""Condition Check: are two conflicting claims comparable, and which condition differs?"""

from dataclasses import dataclass, field
from math import isfinite
from typing import Any

from alloy.contracts import Claim


def measurement_issue(claim: Claim) -> str | None:
    """The current investigation compares relative coefficient error, never runtime or percent."""
    if claim.value is not None:
        if claim.quantity != "coef_error" or claim.unit not in {"relative", "dimensionless"}:
            return "numeric investigation requires coef_error in relative or dimensionless units"
    elif claim.quantity != "equations_recovered" or not claim.outcome:
        return "qualitative investigation requires an equations_recovered outcome"
    return None


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
    assessment: str = "investigable"


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
    if any(value is not None and not isfinite(value) for value in (a.value, b.value)):
        report.comparable = False
        report.notes.append("reported values must be finite")

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
    report.reproducible = [k for k in report.differing if k in adapter_keys]
    unsupported = set(report.differing) - set(adapter_keys)
    if unsupported and adapter_keys:
        report.comparable = False
        report.notes.append("adapter cannot vary: " + ", ".join(sorted(unsupported)))
    if len(report.reproducible) > 1:
        report.notes.append("vary each setting in controlled runs; one-at-a-time attribution can miss interactions")
    if report.differing:
        report.notes.append("condition differences are hypotheses, not proof of the cause")
    if report.comparable and not report.differing:
        report.notes.append("no stated condition explains the gap; check unstated settings")
        report.notes.append("simulation defaults for unstated settings are assumptions, not paper evidence")
        report.assessment = "unstated_settings_hypothesis"
    if not report.comparable:
        report.assessment = "insufficient_evidence" if report.missing else "incompatible"
    return report
