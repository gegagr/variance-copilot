# Contract: LLMProvider port (and OpenRouter adapter)

The agent core depends ONLY on this port. It contains no SDK or HTTP calls. One concrete
adapter ships in this block (`OpenRouterProvider`); a `FakeLLMProvider` drives all tests.

## Port

```python
# agent/provider.py
from typing import Protocol

class LLMProvider(Protocol):
    def complete(
        self,
        messages: list[dict],          # role/content message history
        tools: list[dict],             # JSON tool definitions (incl. query_gl_detail, emit_investigation)
        *,
        temperature: Decimal,
        model: str,
    ) -> "ProviderResponse": ...
```

`ProviderResponse` is exactly one of:

- **ToolCall** — `name: str`, `arguments: dict`, `call_id: str` (the model wants to call a tool).
- **StructuredFinal** — `payload: dict` (the validated arguments of the forced `emit_investigation`
  tool call; the investigation's final answer).

### Guarantees the core relies on

- `complete` is the **only** interaction surface. The core never imports a vendor SDK.
- The adapter MUST NOT include the API key anywhere in `ProviderResponse` or logs.
- Determinism: `temperature` defaults to `0`; the core passes it through from `AgentSettings`.

## OpenRouterProvider (adapter)

- The ONLY module importing `httpx` and reading `OPENROUTER_API_KEY` from the environment.
- Translates `messages` + `tools` into the OpenRouter chat-completions request, parses the
  response into `ToolCall` / `StructuredFinal`.
- The API key is read from the env var at call time; it is never written to the audit log,
  never returned, never committed.

## FakeLLMProvider (tests)

- Constructed with a scripted sequence of `ProviderResponse`s (e.g. one `ToolCall` to
  `query_gl_detail`, then a `StructuredFinal` emitting a Question or Draft).
- No network. Makes the entire investigation loop deterministic and offline.

## Contract tests

- The core, given `FakeLLMProvider`, completes an investigation without any network.
- `OpenRouterProvider` is the only file matching an `httpx`/`OPENROUTER_API_KEY` import scan
  (enforced by `test_architecture`-style guard).
- A response carrying the API key is never produced (redaction asserted in `test_audit`).
