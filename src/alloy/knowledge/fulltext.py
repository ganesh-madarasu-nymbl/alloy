"""Full text for papers Bond finds. Bond returns metadata and abstracts only, so methods text comes
from arXiv's HTML rendering (built from the authors' LaTeX), split into sections and tables.

Equations keep their LaTeX `alttext`, so stated values such as "\\eta = 1" survive extraction.
"""

import json
import re
import time
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from pydantic import BaseModel

from alloy.config import settings

SOURCES = ("https://arxiv.org/html/{id}", "https://ar5iv.labs.arxiv.org/html/{id}")
USER_AGENT = "alloy-hackathon/0.1 (research reproduction tool)"
_ARXIV = re.compile(r"(?:arxiv:)?(\d{4}\.\d{4,5})(?:v\d+)?", re.I)
_last_request = 0.0  # arXiv asks for at most one request every few seconds


class Section(BaseModel):
    title: str
    text: str


class Document(BaseModel):
    paper_id: str
    url: str
    sections: list[Section]

    @property
    def chars(self) -> int:
        return sum(len(s.title) + len(s.text) for s in self.sections)


def arxiv_id(paper: str) -> str | None:
    m = _ARXIV.fullmatch((paper or "").strip())
    return m.group(1) if m else None


class _Parser(HTMLParser):
    """Collect section titles and text from LaTeXML HTML. Tables and captions become their own
    sections so a table is never split from its caption."""

    BLOCK = {"p", "div", "li", "tr", "figcaption", "h1", "h2", "h3", "h4", "h5", "h6", "br"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sections: list[Section] = [Section(title="Front matter", text="")]
        self._skip = 0
        self._title: list[str] | None = None
        self._table: list[str] | None = None
        self._table_depth = 0

    def _emit(self, text: str) -> None:
        if self._title is not None:
            self._title.append(text)
        elif self._table is not None:
            self._table.append(text)
        else:
            self.sections[-1].text += text

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class") or ""
        if tag in ("script", "style", "nav", "header", "footer"):
            self._skip += 1
        elif self._skip:
            return
        elif tag == "math":
            self._emit(f" {a.get('alttext', '')} ")
            self._skip += 1  # alttext already carries the content
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6") and "ltx_title" in cls and self._table is None:
            self._title = []
        elif tag == "figure" and "ltx_table" in cls:
            self._table, self._table_depth = [], 1
        elif tag == "figure" and self._table is not None:
            self._table_depth += 1
        elif tag in ("td", "th"):
            self._emit(" | ")
        elif tag in self.BLOCK:
            self._emit("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "header", "footer", "math"):
            self._skip = max(0, self._skip - 1)
            return
        if self._skip:
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6") and self._title is not None:
            title = " ".join("".join(self._title).split())
            self._title = None
            if title:
                self.sections.append(Section(title=title, text=""))
        elif tag == "figure" and self._table is not None:
            self._table_depth -= 1
            if self._table_depth == 0:
                text = _clean("".join(self._table))
                self._table = None
                caption = text.split("\n", 1)[0][:80]
                self.sections.append(Section(title=f"Table: {caption}", text=text))
                self.sections.append(Section(title=self._resume_title(), text=""))

    def _resume_title(self) -> str:
        titles = [s.title for s in self.sections if not s.title.startswith("Table:")]
        return f"{titles[-1]} (continued)" if titles else "Body"

    def handle_data(self, data):
        if not self._skip:
            self._emit(data)


def _clean(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.split("\n")]
    return "\n".join(line for line in lines if line.strip(" |"))


def parse_html(paper_id: str, url: str, html: str) -> Document:
    parser = _Parser()
    parser.feed(html)
    sections = [Section(title=s.title, text=_clean(s.text)) for s in parser.sections]
    return Document(paper_id=paper_id, url=url, sections=[s for s in sections if s.text])


def _get(url: str) -> str:
    global _last_request
    wait = 3.0 - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return response.read().decode("utf-8", "replace")
    finally:
        _last_request = time.monotonic()


def fetch(paper: str, use_cache: bool = True, cache_dir: Path | None = None) -> Document:
    """Full text for an arXiv paper id, cached on disk. Raises ValueError for non-arXiv ids."""
    pid = arxiv_id(paper)
    if pid is None:
        raise ValueError(f"{paper}: full text is only available for arXiv papers")
    path = Path(cache_dir or settings.cache_dir) / "fulltext" / f"{pid}.json"
    if use_cache and path.exists():
        return Document.model_validate_json(path.read_text(encoding="utf-8"))
    errors = []
    for template in SOURCES:
        url = template.format(id=pid)
        try:
            doc = parse_html(pid, url, _get(url))
        except OSError as exc:
            errors.append(f"{url}: {exc}")
            continue
        if doc.chars > 5000:  # a real paper, not an error or placeholder page
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(doc.model_dump_json(indent=1), encoding="utf-8")
            return doc
        errors.append(f"{url}: page too short to be the paper")
    raise ValueError(f"{paper}: no full text found ({'; '.join(errors)})")


METHOD_TERMS = (
    "noise",
    "variance",
    "threshold",
    "lambda",
    "\\lambda",
    "\\eta",
    "sparsity",
    "initial condition",
    "time step",
    "\\Delta t",
    "dt",
    "sampl",
    "polynomial",
    "library",
    "derivative",
    "finite difference",
    "lorenz",
    "recover",
    "identif",
    "table",
    "trajectory",
    "measurement",
    "gaussian",
    "least squares",
)
SKIP_TITLES = ("references", "bibliography", "acknowledg", "author contributions", "data availability")


def relevant_text(doc: Document, budget_chars: int = 12000, terms: tuple[str, ...] = METHOD_TERMS) -> str:
    """The sections most about the experimental setup, best first, within a character budget.
    Keeps prompts small enough for Groq's free tier (8K tokens a minute)."""

    def score(section: Section) -> float:
        body = section.text.lower()
        hits = sum(body.count(t.lower()) for t in terms) + 3 * sum(t in section.title.lower() for t in terms)
        bonus = 1.5 if section.title.startswith("Table:") else 1.0
        return bonus * hits / (1 + len(body) / 2000)

    candidates = [s for s in doc.sections if not any(k in s.title.lower() for k in SKIP_TITLES)]
    picked, used = [], 0
    for section in sorted(candidates, key=score, reverse=True):
        if score(section) == 0:
            break
        block = f"## {section.title}\n{section.text}"
        if used + len(block) > budget_chars:
            block = block[: max(0, budget_chars - used)]
        if len(block) < 200:
            continue
        picked.append((doc.sections.index(section), block))
        used += len(block)
        if used >= budget_chars:
            break
    return "\n\n".join(block for _, block in sorted(picked))


def save_summary(doc: Document) -> str:
    return json.dumps({"paper": doc.paper_id, "url": doc.url, "sections": len(doc.sections), "chars": doc.chars})
