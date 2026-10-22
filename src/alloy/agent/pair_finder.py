"""Find two real papers that disagree: Bond searches arXiv, the model reads the abstracts, code checks every quote."""

import json
import re
from typing import Literal

from pydantic import BaseModel

from alloy import llm
from alloy.config import settings

MIN_QUOTE = 20  # a quote shorter than this proves nothing about the paper's claim
ATTEMPTS = 2

SYSTEM = (
    "You pick papers for a reproduction audit of sparse-regression equation discovery (SINDy and its variants) "
    "on noisy data, run on the Lorenz system. Use only the candidate papers given. Copy quotes verbatim from the "
    "abstract shown; never paraphrase or join sentences."
)


class Candidate(BaseModel):
    id: str  # arXiv id without version, e.g. 2009.08810
    title: str
    abstract: str
    url: str


class Stance(BaseModel):
    paper: str
    stance: Literal["recovers", "fails"]
    quote: str


class PairChoice(BaseModel):
    stances: list[Stance]
    reason: str


class FoundPair(BaseModel):
    query: str
    candidates: int
    stances: list[Stance]  # the recovering paper first
    titles: dict[str, str]
    urls: dict[str, str]
    reason: str

    @property
    def papers(self) -> tuple[str, str]:
        return tuple(f"arxiv:{s.paper}" for s in self.stances)


class NoPairFound(RuntimeError):
    pass


def search(query: str, limit: int = 20) -> list[Candidate]:
    """Real arXiv papers for the question, from Valency Bond."""
    if not (settings.bond_backend == "http" and settings.bond_configured):
        raise NoPairFound("Bond is not configured, so no papers can be searched.")
    from alloy.knowledge.http_bond import HttpBond

    result = (
        HttpBond()
        .open()
        .call(
            "semantic_search_papers",
            {
                "query": query,
                "limit": limit,
                "source": "arxiv",
                "include_abstract": True,
            },
        )
    )
    if result.get("isError"):
        raise NoPairFound("Bond returned a search error.")
    rows = json.loads(result["content"][0]["text"]).get("papers") or []
    found = []
    for r in rows:
        pid = r.get("base_id") or _bare(str(r.get("id", "")))
        if pid and r.get("abstract"):
            found.append(
                Candidate(
                    id=pid,
                    title=r.get("title") or pid,
                    abstract=r["abstract"],
                    url=r.get("url") or f"https://arxiv.org/abs/{pid}",
                )
            )
    return found


def _bare(pid: str) -> str:
    return re.sub(r"v\d+$", "", pid.strip().removeprefix("arxiv:"))


def _norm(text: str) -> str:
    return " ".join(text.replace("’", "'").replace("–", "-").replace("—", "-").lower().split())


def check(choice: PairChoice, candidates: list[Candidate]) -> list[Stance]:
    """Accept the choice only if code can confirm it: known papers, one per side, quotes found in the abstracts."""
    by_id = {c.id: c for c in candidates}
    by_title = {_norm(c.title): c.id for c in candidates}
    if len(choice.stances) != 2:
        raise NoPairFound(f"expected two papers, got {len(choice.stances)}")
    for s in choice.stances:
        given = s.paper.strip().strip("[]")
        s.paper = by_title.get(_norm(given)) or _bare(given)
        if s.paper not in by_id:
            raise NoPairFound(f"{s.paper} was not in Bond's results")
        if len(s.quote.strip()) < MIN_QUOTE or _norm(s.quote) not in _norm(by_id[s.paper].abstract):
            raise NoPairFound(f"the quote for {s.paper} is not in its abstract")
    if {s.stance for s in choice.stances} != {"recovers", "fails"} or choice.stances[0].paper == choice.stances[
        1
    ].paper:
        raise NoPairFound("the two papers do not take opposite sides")
    return sorted(choice.stances, key=lambda s: s.stance != "recovers")


def _prompt(query: str, candidates: list[Candidate], problem: str | None) -> str:
    listing = "\n\n".join(f"[{c.id}] {c.title}\n{c.abstract}" for c in candidates)
    retry = f"\n\nYour previous answer was rejected: {problem}. Fix that." if problem else ""
    return (
        f"Research question: {query}\n\nCandidate papers from arXiv:\n\n{listing}\n\n"
        "Choose exactly two papers whose abstracts disagree on this question: one whose abstract claims its method "
        "recovers the governing equations under the noise it studies (stance 'recovers'), and one whose abstract "
        "says equation discovery fails, breaks down or degrades as noise grows (stance 'fails'). For each, give the "
        "arXiv id shown in brackets above (digits only, e.g. 2009.08810, not the title) and one verbatim sentence "
        "from that abstract as evidence. Both quotes must be about the factor the question asks about (for a noise "
        "question, both must mention noise); a failure for another reason does not count. In reason, say in one or "
        "two sentences what the disagreement is. If no such pair exists, return an empty stances list."
        + retry
    )


def find(query: str, limit: int = 20) -> FoundPair:
    candidates = search(query, limit)
    if len(candidates) < 2:
        raise NoPairFound(f"Bond returned {len(candidates)} arXiv papers with abstracts; two are needed.")
    problem = None
    for _ in range(ATTEMPTS):
        choice = llm.parse(_prompt(query, candidates, problem), PairChoice, system=SYSTEM)
        if not choice.stances:
            raise NoPairFound(f"No two of the {len(candidates)} papers Bond found disagree on this question.")
        try:
            stances = check(choice, candidates)
        except NoPairFound as exc:
            problem = str(exc)
            continue
        by_id = {c.id: c for c in candidates}
        return FoundPair(
            query=query,
            candidates=len(candidates),
            stances=stances,
            titles={s.paper: by_id[s.paper].title for s in stances},
            urls={s.paper: by_id[s.paper].url for s in stances},
            reason=choice.reason,
        )
    raise NoPairFound(f"No verifiable disagreeing pair: {problem}")
