"""Thin wrapper over the Anthropic SDK so every LLM step uses the same model and checks."""

from functools import cache
from typing import TypeVar

import anthropic
from pydantic import BaseModel

from alloy.config import settings

T = TypeVar("T", bound=BaseModel)


class LLMRefusal(RuntimeError):
    pass


@cache
def client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


def parse(prompt: str, schema: type[T], system: str | None = None, effort: str = "medium") -> T:
    """One structured-output call. Returns a validated instance of `schema`."""
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
