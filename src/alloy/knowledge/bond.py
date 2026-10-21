"""Literature search through the Valency Bond MCP server, with a disk cache so demos replay offline."""

import hashlib
import json

from pydantic import BaseModel, Field

from alloy import llm
from alloy.config import settings


class Paper(BaseModel):
    id: str = Field(description="DOI or arXiv id")
    title: str
    year: int | None = None
    passages: list[str] = Field(default_factory=list, description="Sentences that state results and their conditions")


class PaperList(BaseModel):
    papers: list[Paper]


SEARCH_PROMPT = """Use the Bond tools to find up to {k} papers for this research question:

{query}

Prefer papers that report results under stated conditions (noise level, data size, settings).
For each paper give its DOI or arXiv id, title, year, and quote the passages that state results
together with the conditions they were measured under. Follow citations when that finds
papers that disagree with each other."""


def _cache_path(query: str, k: int, backend: str | None = None):
    key = hashlib.sha1(f"{backend or settings.bond_backend}|{query}|{k}".encode()).hexdigest()[:16]
    return settings.cache_dir / f"bond_{key}.json"


def papers_from_mcp(result: dict) -> list[Paper]:
    """Normalize returned metadata/abstracts; never invent full-text passages."""
    if not isinstance(result, dict):
        raise ValueError("Bond result must be a JSON object")
    if result.get("isError"):
        raise ValueError("Bond search failed; no papers were cached")
    payload = result.get("structuredContent")
    if payload is None:
        for block in result.get("content", []):
            if block.get("type") == "text":
                try:
                    payload = json.loads(block["text"])
                    break
                except (ValueError, KeyError):
                    continue
    if isinstance(payload, dict):
        rows = next((payload[k] for k in ("papers", "results", "data") if isinstance(payload.get(k), list)), None)
    else:
        rows = payload
    if not isinstance(rows, list):
        raise ValueError("Unrecognized Bond result shape; inspect the raw response before using it")
    papers = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Unrecognized Bond paper record; no papers were cached")
        identifier = row.get("doi") or row.get("id") or row.get("arxiv_id")
        title = row.get("title")
        if not isinstance(identifier, str) or not identifier or not isinstance(title, str) or not title:
            raise ValueError("Bond paper is missing a usable identifier or title")
        # The same published work can arrive from arXiv and PubMed. Keep the first
        # ranked record so duplicate indexes cannot look like independent evidence.
        doi = row.get("doi")
        identities = set()
        if isinstance(doi, str) and doi.strip():
            canonical_doi = doi.strip().casefold()
            for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
                canonical_doi = canonical_doi.removeprefix(prefix)
            identities.add(("doi", canonical_doi.strip()))
        record_id = row.get("base_id") or row.get("id") or row.get("arxiv_id")
        if isinstance(record_id, str) and record_id.strip():
            identities.add(("record", row.get("source"), record_id.strip()))
        duplicate = bool(identities & seen)
        seen.update(identities)
        if duplicate:
            continue
        abstract = row.get("abstract")
        papers.append(Paper(
            id=identifier, title=title,
            # Abstract-only discovery is insufficient to establish detailed experimental conditions.
            passages=[abstract] if isinstance(abstract, str) and abstract.strip() else [],
        ))
    return papers


def cache_mcp_result(query: str, k: int, result: dict):
    if not query.strip() or not 1 <= k <= 100:
        raise ValueError("Provide a nonempty research query and a limit from 1 to 100")
    papers = papers_from_mcp(result)
    path = _cache_path(query, k, backend="codex")
    path.with_suffix(".raw.json").write_text(json.dumps({
        "backend": "codex", "server": "valency", "tool": "semantic_search_papers",
        "query": query, "limit": k, "evidence": "metadata_and_abstracts", "result": result,
    }, indent=2))
    path.write_text(PaperList(papers=papers).model_dump_json(indent=2))
    return path, papers


def search(query: str, k: int = 8, use_cache: bool = True) -> list[Paper]:
    if not query.strip() or not 1 <= k <= 100:
        raise ValueError("Provide a nonempty research query and a limit from 1 to 100")
    path = _cache_path(query, k)
    if use_cache and path.exists():
        return PaperList.model_validate_json(path.read_text(encoding="utf-8")).papers
    if settings.bond_backend == "codex":
        from alloy.knowledge.codex_bond import search_raw

        result = search_raw(query, k)
        _, papers = cache_mcp_result(query, k, result)
        return papers
    if settings.bond_backend != "claude":
        raise ValueError("ALLOY_BOND_BACKEND must be codex or claude")
    if not settings.bond_configured:
        raise RuntimeError("VALENCY_MCP_URL is not set; see .env.example")

    server = {"type": "url", "url": settings.valency_mcp_url, "name": "bond"}
    if settings.valency_token:
        server["authorization_token"] = settings.valency_token

    response = llm.client().beta.messages.create(
        model=settings.model,
        max_tokens=16000,
        betas=["mcp-client-2025-11-20", "server-side-fallback-2026-07-01"],
        fallbacks="default",
        mcp_servers=[server],
        tools=[{"type": "mcp_toolset", "mcp_server_name": "bond"}],
        output_config={"effort": "medium"},
        messages=[{"role": "user", "content": SEARCH_PROMPT.format(query=query, k=k)}],
    )
    if response.stop_reason == "refusal":
        raise llm.LLMRefusal("Bond search declined")
    notes = "".join(block.text for block in response.content if block.type == "text")

    # Second pass turns the free-text findings into the Paper schema.
    papers = llm.parse(
        f"Convert these literature notes into the schema. Keep quotes verbatim.\n\n{notes}",
        PaperList,
        effort="low",
    ).papers
    path.write_text(json.dumps({"papers": [p.model_dump() for p in papers]}, indent=2), encoding="utf-8")
    return papers
