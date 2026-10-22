import io
import json
import urllib.error
from dataclasses import replace

import pytest
from pydantic import BaseModel

from alloy import llm
from alloy.knowledge import http_bond
from alloy.knowledge.extract import anchor_quote


class Pick(BaseModel):
    method: str
    value: float


def reply(content=None, tool_calls=None):
    message = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {
        "choices": [{"message": message}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 2},
    }


@pytest.fixture
def groq(monkeypatch):
    monkeypatch.setattr(
        llm, "settings", replace(llm.settings, model="openai/gpt-oss-120b")
    )


def test_parse_retries_once_then_validates(groq, monkeypatch):
    replies = iter([reply("not json"), reply('{"method": "sindy", "value": 0.1}')])
    monkeypatch.setattr(llm, "chat", lambda *a, **k: next(replies))
    assert llm.parse("x", Pick) == Pick(method="sindy", value=0.1)


def test_parse_refuses_after_two_bad_outputs(groq, monkeypatch):
    monkeypatch.setattr(llm, "chat", lambda *a, **k: reply('{"method": 1}'))
    with pytest.raises(llm.LLMRefusal):
        llm.parse("x", Pick)


def test_tool_loop_runs_typed_tools_until_done(groq, monkeypatch):
    seen = []

    def run_experiment(method: str, noise: float = 0.0) -> str:
        """Run one experiment."""
        seen.append((method, noise))
        return json.dumps({"error": 0.1})

    call = {
        "id": "c1",
        "type": "function",
        "function": {"name": "run_experiment", "arguments": '{"method": "sindy"}'},
    }
    replies = iter([reply(tool_calls=[call]), reply("done")])
    monkeypatch.setattr(llm, "chat", lambda *a, **k: next(replies))
    usage = list(
        llm.tool_loop("sys", "go", [run_experiment], lambda: False, max_turns=5)
    )
    assert seen == [("sindy", 0.0)] and len(usage) == 2
    spec = llm.tool_spec(run_experiment)["function"]
    assert (
        spec["parameters"]["required"] == ["method"]
        and spec["description"] == "Run one experiment."
    )


class Response(io.BytesIO):
    headers = {"Content-Type": "application/json", "Mcp-Session-Id": "s1"}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_http_bond_refreshes_expired_token_and_keeps_new_pair(monkeypatch, tmp_path):
    monkeypatch.setattr(
        http_bond,
        "settings",
        replace(
            http_bond.settings,
            cache_dir=tmp_path,
            valency_mcp_url="https://bond.test/",
            valency_token="old",
        ),
    )
    monkeypatch.setenv("VALENCY_CLIENT_ID", "client")
    monkeypatch.setenv("VALENCY_REFRESH_TOKEN", "refresh-1")
    auths = []

    def urlopen(req, timeout):
        if req.full_url == http_bond.TOKEN_URL:
            return Response(
                json.dumps(
                    {"access_token": "new", "refresh_token": "refresh-2"}
                ).encode()
            )
        auths.append(req.headers["Authorization"])
        if req.headers["Authorization"] == "Bearer old":
            raise urllib.error.HTTPError(req.full_url, 401, "expired", {}, None)
        return Response(
            json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}).encode()
        )

    monkeypatch.setattr(http_bond.urllib.request, "urlopen", urlopen)
    assert http_bond.HttpBond().request("ping") == {"ok": True}
    assert auths == ["Bearer old", "Bearer new"]
    assert (
        json.loads((tmp_path / ".valency_tokens.json").read_text())["refresh_token"]
        == "refresh-2"
    )


SOURCE = (
    "For example, it discovers the correct sparse libraries in the Lorenz system, with median coefficient "
    "estimate errors equal to 1% - 3% (for 50% noise), 6% - 8% (for 100% noise); and 23% - 25% (for 300% noise). "
    "The enabling modules are robust."
)


@pytest.mark.parametrize("quote", [
    "discover the correct sparse libraries in the Lorenz system, with median coefficient estimate errors",
    "median coefficient estimate errors equal to 6% - 8% (for 100% noise)",
])
def test_trimmed_or_spliced_quotes_anchor_to_the_source_sentence(quote):
    assert anchor_quote(quote, [SOURCE]).startswith("For example, it discovers")


def test_quotes_the_paper_never_states_are_still_rejected():
    assert anchor_quote("Weak SINDy reached 0.1% error on the Rossler system", [SOURCE]) is None
    assert anchor_quote("The enabling modules are robust.", [SOURCE]) == "The enabling modules are robust."
