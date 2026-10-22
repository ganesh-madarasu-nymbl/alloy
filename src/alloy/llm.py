"""Thin LLM wrapper so every step uses the same model and checks.

Claude models go through the Anthropic SDK; any other model goes to an OpenAI-compatible
endpoint (Groq by default), so Alloy and the baseline run on the same free open model.
"""

import inspect
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from functools import cache
from typing import TypeVar

import anthropic
from pydantic import BaseModel, create_model

from alloy.config import settings

T = TypeVar("T", bound=BaseModel)


class LLMRefusal(RuntimeError):
    pass


@cache
def client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


def is_claude() -> bool:
    return settings.model.startswith("claude")


def chat(messages: list[dict], effort: str = "medium", **extra) -> dict:
    """One OpenAI-compatible chat completion, waiting out rate limits instead of failing."""
    body = {"model": settings.model, "messages": messages, "max_completion_tokens": settings.max_tokens, **extra}
    if "gpt-oss" in settings.model:
        body["reasoning_effort"] = effort
    headers = {"Authorization": f"Bearer {settings.llm_api_key}", "Content-Type": "application/json",
               "User-Agent": "alloy"}
    for attempt in range(6):
        req = urllib.request.Request(f"{settings.llm_base_url}/chat/completions", json.dumps(body).encode(), headers)
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as exc:
            text = exc.read().decode(errors="replace")
            if exc.code == 429 or exc.code >= 500:
                time.sleep(min(float(exc.headers.get("retry-after") or 2**attempt), 60))
                continue
            if exc.code == 400 and "json_validate_failed" in text:
                raise ValueError("model output failed the response schema") from exc
            raise RuntimeError(f"LLM request failed ({exc.code}): {text[:300]}") from exc
    raise RuntimeError("LLM rate limit persisted; try again in a minute")


def parse(prompt: str, schema: type[T], system: str | None = None, effort: str = "medium") -> T:
    """One structured-output call. Returns a validated instance of `schema`."""
    if not is_claude():
        messages = [{"role": "system", "content": system}] if system else []
        messages.append({"role": "user", "content": prompt})
        fmt = {"type": "json_schema", "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()}}
        error: Exception | None = None
        for _ in range(2):
            try:
                reply = chat(messages, effort, response_format=fmt)
                return schema.model_validate_json(reply["choices"][0]["message"].get("content") or "")
            except ValueError as exc:  # pydantic ValidationError is a ValueError
                error = exc
        raise LLMRefusal(f"model output did not match {schema.__name__}: {error}")
    kwargs = {"system": system} if system else {}
    response = client().messages.parse(
        model=settings.model,
        max_tokens=16000,
        output_config={"effort": effort},
        messages=[{"role": "user", "content": prompt}],
        output_format=schema,
        **kwargs,
    )
    if response.stop_reason == "refusal":
        raise LLMRefusal(getattr(response.stop_details, "explanation", "model declined"))
    return response.parsed_output


def tool_spec(fn: Callable) -> dict:
    """OpenAI function schema from a plain typed function and its docstring."""
    params = inspect.signature(fn).parameters
    fields = {n: (p.annotation, ... if p.default is p.empty else p.default) for n, p in params.items()}
    schema = create_model(fn.__name__, **fields).model_json_schema()
    function = {"name": fn.__name__, "description": inspect.getdoc(fn), "parameters": schema}
    return {"type": "function", "function": function}


def tool_loop(system: str, prompt: str, tools: list[Callable], done: Callable[[], bool], max_turns: int,
              effort: str = "medium") -> Iterator[dict]:
    """Let the model call `tools` until done() or it stops calling them; yields usage per turn."""
    specs, by_name = [tool_spec(f) for f in tools], {f.__name__: f for f in tools}
    messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    for _ in range(max_turns):
        message = (reply := chat(messages, effort, tools=specs))["choices"][0]["message"]
        yield reply.get("usage", {})
        calls = message.get("tool_calls") or []
        messages.append({k: message[k] for k in ("role", "content", "tool_calls") if message.get(k) is not None})
        if not calls:
            return
        for call in calls:
            fn = by_name.get(call["function"]["name"])
            try:
                out = fn(**json.loads(call["function"]["arguments"] or "{}")) if fn else "unknown tool"
            except (TypeError, ValueError) as exc:
                out = json.dumps({"error": str(exc)})
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": out})
        if done():
            return
