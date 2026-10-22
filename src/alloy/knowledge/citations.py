"""BibTeX for cited papers, exported from Valency Bond and cached so reports build offline."""

import json
import re
from pathlib import Path

from alloy.config import settings

_ARXIV = re.compile(r"(?:arxiv:)?(\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?", re.I)
_DOI = re.compile(r"(?:doi:\s*|https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/\S+)", re.I)


def bond_id(paper: str) -> str | None:
    """The id Bond's export accepts, or None for synthetic and unrecognised ids."""
    paper = (paper or "").strip()
    if m := _ARXIV.fullmatch(paper):
        return m.group(1)
    if m := _DOI.fullmatch(paper):
        return m.group(1)
    if paper.isdigit():  # PubMed id
        return paper
    return None


def _cache_file(cache_path: Path | None) -> Path:
    return Path(cache_path) if cache_path else settings.cache_dir / "bibtex.json"


def _load(path: Path) -> dict[str, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}
    except (OSError, ValueError):
        return {}


def _export(ids: list[str]) -> dict[str, str]:
    from alloy.knowledge.http_bond import HttpBond

    result = HttpBond().open().call("export_papers_bibtex", {"paper_ids": ids})
    payload = json.loads(result["content"][0]["text"])
    found = {}
    for entry in payload.get("entries", []):
        base = re.sub(r"v\d+$", "", str(entry.get("id", "")))
        if base and entry.get("bibtex"):
            found[base] = entry["bibtex"]
    # Bond answers DOIs and PubMed ids under its own id; match those back by DOI or position.
    for wanted in ids:
        if wanted not in found:
            for entry in payload.get("entries", []):
                if wanted.lower() in entry.get("bibtex", "").lower():
                    found[wanted] = entry["bibtex"]
                    break
    return found


def bibtex(papers: list[str], fetch: bool = False, cache_path: Path | None = None) -> dict[str, str]:
    """Paper id -> BibTeX entry. Only calls Bond when `fetch` is set and the direct HTTP backend is
    configured; otherwise returns cached entries. Never raises: a report must build without Bond."""
    path = _cache_file(cache_path)
    cache = _load(path)
    wanted = {p: bond_id(p) for p in dict.fromkeys(papers)}
    missing = sorted({b for b in wanted.values() if b and b not in cache})
    if missing and fetch and settings.bond_backend == "http" and settings.bond_configured:
        try:
            cache.update(_export(missing))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")
        except Exception:  # noqa: BLE001 - citations are optional; the audit must still be written
            pass
    return {paper: cache[b] for paper, b in wanted.items() if b and b in cache}
