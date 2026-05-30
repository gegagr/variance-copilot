"""FakeLLMProvider for deterministic, offline agent-logic tests.

Constructed with a scripted sequence of provider responses (tool calls / finals). May
also be scripted to raise (to exercise the fail-safe path). No network.
"""

from __future__ import annotations

from decimal import Decimal

from agent.provider import StructuredFinal, ToolCall


def tool_call(name: str, arguments: dict, call_id: str = "call") -> ToolCall:
    return ToolCall(name=name, arguments=arguments, call_id=call_id)


def final(payload: dict) -> StructuredFinal:
    return StructuredFinal(payload=payload)


class FakeLLMProvider:
    """Returns scripted responses in order. An item that is an ``Exception`` is raised."""

    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    def complete(self, messages, tools, *, temperature: Decimal, model: str):
        self.calls.append({"messages": messages, "tools": tools, "model": model})
        if not self._responses:
            raise AssertionError("FakeLLMProvider exhausted: no scripted response left")
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt
