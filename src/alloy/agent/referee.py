"""Referee agent: argues against a verdict the way a skeptical reviewer would."""

from pydantic import BaseModel, Field

from alloy import llm


class RefereeReport(BaseModel):
    objections: list[str] = Field(description="Concrete problems with the verdict, most serious first")
    verdict_holds: bool


SYSTEM = """You are a skeptical referee for a physics venue. Find the strongest reasons the
verdict could be wrong: unfair comparisons, conditions that were not controlled, too few seeds,
metrics that hide failures, or claims that go beyond the evidence. Do not invent results."""


def review(investigation) -> list[str]:
    report = llm.parse(
        "Review this investigation record:\n\n" + investigation.model_dump_json(indent=1),
        RefereeReport,
        system=SYSTEM,
        effort="high",
    )
    prefix = [] if report.verdict_holds else ["Referee: verdict does not hold as stated."]
    return prefix + report.objections
