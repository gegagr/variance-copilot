"""LLMProvider port + OpenRouter adapter.

The agent CORE depends only on the `LLMProvider` Protocol and the `ProviderResponse`
types defined here — never on a vendor SDK. `OpenRouterProvider` is the ONLY place that
imports `httpx` and reads the API key (kept in this same file but never used by the core).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol, Union, runtime_checkable

# tool_choice value that FORCES the model to emit the structured investigation result.
FORCE_EMIT = {"type": "function", "function": {"name": "emit_investigation"}}


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict
    call_id: str = "call"


@dataclass(frozen=True)
class StructuredFinal:
    payload: dict


@dataclass(frozen=True)
class TextResponse:
    """A prose completion (finish_reason "stop", no tool call). NOT grounded output — the loop
    must re-prompt forcing the emit tool, or fail safe."""

    content: str


ProviderResponse = Union[ToolCall, StructuredFinal, TextResponse]


@runtime_checkable
class LLMProvider(Protocol):
    def complete(
        self,
        messages: list[dict],
        tools: list[dict],
        *,
        temperature: Decimal,
        model: str,
        tool_choice: Union[str, dict] = "auto",
    ) -> ProviderResponse: ...


# --------------------------------------------------------------------------- #
# OpenRouter adapter — the ONLY network/SDK site (imports httpx, reads the key).
# --------------------------------------------------------------------------- #
class OpenRouterError(RuntimeError):
    pass


@dataclass
class OpenRouterProvider:
    """Concrete `LLMProvider` over the OpenRouter chat-completions API.

    The API key is read from ``OPENROUTER_API_KEY`` at call time and is never returned,
    logged, or stored on the instance.
    """

    base_url: str = "https://openrouter.ai/api/v1"
    _emit_tool_name: str = field(default="emit_investigation", repr=False)

    def complete(
        self,
        messages: list[dict],
        tools: list[dict],
        *,
        temperature: Decimal,
        model: str,
        tool_choice: Union[str, dict] = "auto",
    ) -> ProviderResponse:
        import httpx  # imported lazily so the core never pulls in httpx

        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise OpenRouterError("OPENROUTER_API_KEY is not set")

        payload = {
            "model": model,
            "messages": messages,
            "tools": tools,
            "temperature": float(temperature),
            "tool_choice": tool_choice,
        }
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return self._parse(data)

    def _parse(self, data: dict) -> ProviderResponse:
        try:
            choice = data["choices"][0]
            message = choice["message"]
        except (KeyError, IndexError) as exc:
            raise OpenRouterError(f"malformed OpenRouter response: {exc}") from exc

        calls = message.get("tool_calls") or []
        if not calls:
            # The model answered in prose instead of calling a tool. This is NOT an error to
            # swallow — return it so the loop can force structured output or fail safe.
            return TextResponse(content=message.get("content") or "")

        try:
            call = calls[0]
            name = call["function"]["name"]
            import json

            arguments = json.loads(call["function"]["arguments"])
        except (KeyError, ValueError) as exc:
            raise OpenRouterError(f"malformed tool call in OpenRouter response: {exc}") from exc

        if name == self._emit_tool_name:
            return StructuredFinal(payload=arguments)
        return ToolCall(name=name, arguments=arguments, call_id=call.get("id", "call"))
