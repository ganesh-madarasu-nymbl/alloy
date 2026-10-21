import asyncio
import json
from dataclasses import replace
from unittest.mock import AsyncMock, Mock

import pytest

from alloy.knowledge import bond, codex_bond


def payload():
    return {"structuredContent": {"papers": [{
        "id": "arxiv:1234.56789", "title": "Fixture paper",
        "abstract": "This fixture studies sparse equation recovery.",
    }]}}


def test_codex_search_caches_raw_evidence_and_replays_without_model(monkeypatch, tmp_path):
    monkeypatch.setattr(bond, "settings", replace(bond.settings, bond_backend="codex", cache_dir=tmp_path))
    calls = []

    def search(query, limit):
        calls.append((query, limit))
        return payload()

    monkeypatch.setattr(codex_bond, "search_raw", search)
    monkeypatch.setattr(bond.llm, "client", lambda: pytest.fail("No model client should run"))
    first = bond.search("sparse equations", 3)
    assert bond.search("sparse equations", 3) == first
    assert calls == [("sparse equations", 3)]
    raw = json.loads(next(tmp_path.glob("*.raw.json")).read_text())
    assert raw["tool"] == "semantic_search_papers"
    assert raw["evidence"] == "metadata_and_abstracts"
    assert first[0].passages == [payload()["structuredContent"]["papers"][0]["abstract"]]


@pytest.mark.parametrize("result", [
    {"isError": True}, {"structuredContent": {"unexpected": []}},
    {"structuredContent": {"papers": [{"title": "No ID"}]}},
])
def test_bad_results_do_not_create_cache(monkeypatch, tmp_path, result):
    monkeypatch.setattr(bond, "settings", replace(bond.settings, cache_dir=tmp_path))
    with pytest.raises(ValueError):
        bond.cache_mcp_result("query", 3, result)
    assert not list(tmp_path.iterdir())


def test_metadata_is_not_invented_as_full_text():
    result = {"content": [{"type": "text", "text": json.dumps({
        "results": [{"doi": "10.1234/fixture", "title": "Metadata only"}],
    })}]}
    assert bond.papers_from_mcp(result)[0].passages == []


def test_search_uses_ephemeral_thread_and_only_research_tool():
    async def run():
        client = codex_bond.CodexBond()
        client.request = AsyncMock(side_effect=[
            {"thread": {"id": "fixture"}},
            {"data": [{"name": "valency", "tools": {"semantic_search_papers": {}}}]},
            payload(),
        ])
        assert await client.search("equations", 5) == payload()
        calls = client.request.call_args_list
        assert calls[0].args[1]["ephemeral"] is True
        assert calls[0].args[1]["sandbox"] == "read-only"
        assert [c.args[0] for c in calls] == ["thread/start", "mcpServerStatus/list", "mcpServer/tool/call"]
        assert calls[-1].args[1]["tool"] == "semantic_search_papers"
    asyncio.run(run())


def test_empty_inventory_is_unverified():
    async def run():
        client = codex_bond.CodexBond()
        client.request = AsyncMock(return_value={"data": [{"name": "valency", "tools": {}}]})
        with pytest.raises(codex_bond.BondConnectionError, match="no tools"):
            await client.inventory()
    asyncio.run(run())


def test_protocol_declines_interactive_requests():
    async def run():
        client = codex_bond.CodexBond()
        client.send = AsyncMock()
        reader = asyncio.StreamReader()
        reader.feed_data(b'{"id":99,"method":"mcpServer/elicitation/request","params":{}}\n')
        reader.feed_eof()

        class Process:
            stdout = reader

        client.process = Process()
        with pytest.raises(codex_bond.BondConnectionError, match="interactive"):
            await client.request("mcpServerStatus/list", {})
        reply = client.send.call_args_list[-1].args[0]
        assert reply["id"] == 99
        assert "error" in reply
    asyncio.run(run())


def test_failed_start_cleans_up_process(monkeypatch):
    async def run():
        class Process:
            returncode = None
            stdin = Mock(drain=AsyncMock())
            stdout = AsyncMock()
            terminate = AsyncMock()
            wait = AsyncMock()

        process = Process()
        process.terminate = lambda: setattr(process, "returncode", 1)
        process.stdout.readline.return_value = b""
        monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
        with pytest.raises(codex_bond.BondConnectionError, match="could not start"):
            async with codex_bond.CodexBond():
                pytest.fail("Failed bridge must not be usable")
        process.wait.assert_awaited_once()
    asyncio.run(run())
