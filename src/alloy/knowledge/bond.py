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


def _cache_path(query: str, k: int):
    key = hashlib.sha1(f"{query}|{k}".encode()).hexdigest()[:16]
    return settings.cache_dir / f"bond_{key}.json"


def search(query: str, k: int = 8, use_cache: bool = True) -> list[Paper]:
    path = _cache_path(query, k)
    if use_cache and path.exists():
        return PaperList.model_validate_json(path.read_text(encoding="utf-8")).papers
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
