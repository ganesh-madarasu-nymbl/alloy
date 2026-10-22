"""Find two real papers that disagree: Bond searches arXiv, the model shortlists from the abstracts, code checks
every quote, and Alloy reads the full texts until one paper reports standard SINDy recovering and another failing.
"""

import json
import re
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from itertools import zip_longest
from typing import Literal

from pydantic import BaseModel

from alloy import llm
from alloy.config import settings

MIN_QUOTE = 20  # a quote shorter than this proves nothing about the paper's claim
SHORTLIST = 6
SCOPE_QUERY = "sparse identification of nonlinear dynamics Lorenz noise"
MAX_READS = 6  # full texts read per search; each costs one model call unless already extracted

SYSTEM = (
    "You shortlist papers for a reproduction audit of standard SINDy (sequential thresholded least squares) on "
    "noisy Lorenz data. Use only the candidate papers given. Copy quotes verbatim from the abstract shown; never "
    "paraphrase or join sentences."
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


class Shortlist(BaseModel):
    papers: list[Stance]
    reason: str = ""


class FoundPair(BaseModel):
    query: str
    candidates: int
    stances: list[Stance]  # the recovering paper first; stance and quote come from the full text
    titles: dict[str, str]
    urls: dict[str, str]
    reason: str
    checked: list[str] = []  # what each full text read said, in order

    @property
    def papers(self) -> tuple[str, str]:
        return tuple(f"arxiv:{s.paper}" for s in self.stances)


class NoPairFound(RuntimeError):
    pass


def search(query: str, limit: int = 25) -> list[Candidate]:
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
    return re.sub(r"v\d+$", "", pid.strip().strip("[]").removeprefix("arxiv:"))


def _norm(text: str) -> str:
    return " ".join(text.replace("’", "'").replace("–", "-").replace("—", "-").lower().split())


def check(shortlist: Shortlist, candidates: list[Candidate]) -> tuple[list[Stance], list[str]]:
    """Keep only picks code can confirm: a paper Bond returned, a quote found in its abstract. Returns kept, dropped."""
    by_id = {c.id: c for c in candidates}
    by_title = {_norm(c.title): c.id for c in candidates}
    kept, dropped, seen = [], [], set()
    for s in shortlist.papers:
        s.paper = by_title.get(_norm(s.paper)) or _bare(s.paper)
        if s.paper not in by_id:
            dropped.append(f"{s.paper}: not in Bond's results")
        elif len(s.quote.strip()) < MIN_QUOTE or _norm(s.quote) not in _norm(by_id[s.paper].abstract):
            dropped.append(f"{s.paper}: quote not in its abstract")
        elif s.paper not in seen:
            seen.add(s.paper)
            kept.append(s)
    return kept, dropped


def _prompt(query: str, candidates: list[Candidate]) -> str:
    listing = "\n\n".join(f"[{c.id}] {c.title}\n{c.abstract}" for c in candidates)
    return (
        f"Research question: {query}\n\nCandidate papers from arXiv:\n\n{listing}\n\n"
        f"Shortlist up to {SHORTLIST} papers, most promising first, whose full text most likely reports how standard "
        "SINDy performs on noisy Lorenz data: stance 'recovers' if the abstract suggests standard SINDy identifies "
        "the equations under the noise studied, 'fails' if it suggests standard SINDy breaks down as noise grows "
        "(papers proposing a noise-robust variant usually report this). Include both stances. For each, give the "
        "arXiv id shown in brackets (digits only, e.g. 2009.08810, not the title) and one verbatim sentence from "
        "that abstract as evidence. In reason, say in one sentence what the papers disagree about. If no paper "
        "fits, return an empty list."
    )


def _read(paper: str) -> tuple[str | None, str, str]:
    """Standard-SINDy outcome stated in the paper's full text: (result or None, quote, noise as written)."""
    from alloy.agent.real_pair import load_protocol

    proto, _ = load_protocol(f"arxiv:{paper}")
    if proto.outcome is None:
        return None, "", ""
    return proto.outcome.result, proto.outcome.quote, proto.outcome.noise_as_written


def _extracted(paper: str) -> bool:
    """Whether the paper's settings are already extracted and committed, so reading it is instant."""
    from alloy.knowledge import protocol

    return protocol.load_committed(f"arxiv:{paper}") is not None


def _outcomes(order: list[str], ready: list[str], read: Callable) -> Iterator[tuple[str, tuple | Exception]]:
    """Read already-extracted papers first; only if no pair is found yet, read the rest three at a time."""

    def attempt(paper: str) -> tuple | Exception:
        try:
            return read(paper)
        except Exception as exc:  # noqa: BLE001 - one unreadable paper should not end the search
            return exc

    for paper in ready:
        yield paper, attempt(paper)
    pool = ThreadPoolExecutor(max_workers=3)
    try:
        futures = {p: pool.submit(attempt, p) for p in order if p not in ready}
        for paper, future in futures.items():
            yield paper, future.result()
    finally:
        pool.shutdown(wait=False, cancel_futures=True)  # a found pair returns at once; unread papers are dropped


def find(
    query: str,
    limit: int = 25,
    read: Callable[[str], tuple[str | None, str, str]] = _read,
    extracted: Callable[[str], bool] = _extracted,
) -> FoundPair:
    candidates = search(query, limit)
    # Alloy can only rerun standard SINDy on Lorenz, so it also asks Bond for papers on that method directly.
    seen = {c.id for c in candidates}
    candidates += [c for c in search(SCOPE_QUERY, limit) if c.id not in seen]
    if len(candidates) < 2:
        raise NoPairFound(f"Bond returned {len(candidates)} arXiv papers with abstracts; two are needed.")
    try:
        shortlist = llm.parse(_prompt(query, candidates), Shortlist, system=SYSTEM)
    except Exception as exc:  # noqa: BLE001 - papers already read can still be paired
        shortlist = Shortlist(papers=[], reason=f"shortlist failed ({type(exc).__name__})")
    kept, checked = check(shortlist, candidates)
    hints = {h: [s.paper for s in kept if s.stance == h] for h in ("recovers", "fails")}
    order = [p for pair in zip_longest(hints["recovers"], hints["fails"]) for p in pair if p]
    order += [c.id for c in candidates if c.id not in order and extracted(c.id)]
    ready = [p for p in order if extracted(p)]  # already-read papers first: no model call, no wait
    order = (ready + [p for p in order if p not in ready])[: MAX_READS + len(ready)]
    by_id = {c.id: c for c in candidates}
    stated: dict[str, tuple[Stance, str]] = {}
    for paper, outcome in _outcomes(order, ready, read):
        if isinstance(outcome, Exception):
            checked.append(f"{paper}: full text unreadable ({type(outcome).__name__})")
            continue
        result, quote, level = outcome
        if result is None:
            checked.append(f"{paper}: full text states no standard-SINDy result")
            continue
        checked.append(f"{paper}: full text says standard SINDy {result} at noise {level}")
        stated.setdefault(result, (Stance(paper=paper, stance=result, quote=quote), level))
        if len(stated) == 2:
            (rec, rec_noise), (fail, fail_noise) = stated["recovers"], stated["fails"]
            return FoundPair(
                query=query,
                candidates=len(candidates),
                stances=[rec, fail],
                titles={x.paper: by_id[x.paper].title for x in (rec, fail)},
                urls={x.paper: by_id[x.paper].url for x in (rec, fail)},
                reason=(
                    f"In their full texts, {rec.paper} reports standard SINDy recovers the equations at noise "
                    f"{rec_noise}, and {fail.paper} reports it fails at noise {fail_noise}."
                ),
                checked=checked,
            )
    raise NoPairFound(
        f"Read {len(order)} of {len(candidates)} papers Bond found; none pair a stated recovery with a stated "
        "failure of standard SINDy. " + "; ".join(checked)
    )
