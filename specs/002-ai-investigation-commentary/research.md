# Phase 0 Research: AI Investigation and Commentary Layer (Block 3)

The three clarify-session decisions (reference-and-render numbers, code-computed aggregates
allowed, embedded evidence snapshots) are already encoded in the spec. This research resolves
*how* to realize them under the constitution with the chosen stack.

---

## R1. Keeping the LLM away from numbers — reference-and-render

**Decision**: The model never emits numeric digits. Structured output carries **figure
references**, not values: a Question/Draft is returned as structured fields where any figure is
a token like `{{fig:flag.current_value}}`, `{{fig:gl:<txn_id>.amount}}`, or
`{{fig:agg:<agg_id>}}`. Deterministic code in `commentary.py` resolves each token to a value
from the allowed source set and substitutes the rendered string. The model also returns the
*narrative* text with these tokens embedded.

**Rationale**: Determinism First — "if a number reaches the screen, a Python function created
it." Reference-and-render makes that literally true: the LLM chooses *which* figure and *where*,
code supplies the digits. The traceability guard (R3) is then a backstop, not the sole defense.

**Alternatives considered**: Free-text numbers validated post-hoc (model still types numbers —
weaker; rejected as primary). No-numbers-at-all structured fields (too rigid for natural prose).

## R2. Allowed figures and code-computed aggregates

**Decision**: The allowed value set for a flag is:
1. **Verbatim source values** — the flag's Block 1 figures (current, comparator, abs/pct/pp
   variance, thresholds) and the `amount` of every GL row returned by that flag's queries.
2. **Code-computed aggregates** — `sum` / `count` / `min` / `max` over an explicit list of cited
   GL evidence row ids. The model supplies `{op, [txn_ids]}`; `commentary.py` computes the
   aggregate with `Decimal` and assigns it an `agg_id`. The model references `{{fig:agg:<id>}}`.

Aggregates are computed and verified by Python — the model never sees or types the result.

**Rationale**: Q2 clarification. Controllers naturally say "the top three invoices total €X";
allowing code-computed aggregates keeps commentary useful while the number is still
Python-created (Determinism First intact). The op set is closed and trivially reproducible.

**Alternatives considered**: Source-values-only (too restrictive — no "total of N invoices");
arbitrary model arithmetic (forbidden — violates Determinism First).

## R3. The traceability guard (deterministic, most-tested unit)

**Decision**: `guards.py` exposes a pure function
`assert_grounded(text, allowed_values, recompute_aggregates) -> GuardResult`. It (a) extracts
every numeric literal from the *fully rendered* text via a currency/number regex, (b) normalizes
each to `Decimal` (strip currency symbol, thousands separators; honor decimals/sign), and (c)
asserts membership in the allowed set — verbatim values plus independently recomputed
aggregates. Any unmatched number → `GuardResult(ok=False, offending=[...])`; the output is
rejected (not shown), logged, and eligible for one bounded retry. The guard also runs on
pre-render output to assert the model emitted **no raw digits** outside tokens.

**Rationale**: This is the constitution's hard line in code (FR-015). Running it on both the
token form (no stray digits) and the rendered form (every number traces) closes both holes.
Pure and deterministic → exhaustively testable, including adversarial inputs.

**Alternatives considered**: Trusting structured output alone (no defense against a hallucinated
digit in a free-text field); LLM self-checks (non-deterministic — rejected).

## R4. Number extraction & normalization

**Decision**: A single regex recognizes optional currency symbol (`€`), sign, grouped integer
part (`1,234,567`), and optional decimals; percentages (`12.3%`) normalize to the ratio form
Block 1 stores (e.g. `0.123`). Comparison is exact `Decimal` equality after quantizing to the
Block 1 precisions (money 2dp, ratio 6dp). Year-like tokens and ids that are not figures are
excluded by requiring a currency/percent context or by an explicit allowlist of non-figure
tokens (dates rendered as ISO are matched structurally, not numerically).

**Rationale**: The guard must not produce false positives on dates/ids nor false negatives on
disguised figures. Normalizing to Block 1 precision makes equality robust.

**Alternatives considered**: Token-level structured rendering only (still need the regex backstop
for free-text narrative). NLP number parsing libs (overkill; non-deterministic edge behavior).

## R5. LLMProvider port and OpenRouter adapter

**Decision**: `LLMProvider` is a Protocol with one method:
`complete(messages, tools, *, temperature, model) -> ProviderResponse`, where `ProviderResponse`
is either a `ToolCall(name, arguments)` or a `StructuredFinal(payload)`. `OpenRouterProvider`
implements it over the OpenRouter chat-completions API using `httpx`, reading the key from
`OPENROUTER_API_KEY`. The adapter is the ONLY module importing `httpx` or reading the env key.
`FakeLLMProvider` (in `agent/fakes.py`) returns a scripted sequence of tool calls / finals for
deterministic offline tests.

**Rationale**: Hexagonal architecture. A one-method port keeps the core trivially mockable and
provider-swappable (OpenRouter today, anything later) with no core change.

**Alternatives considered**: Importing a vendor SDK directly in the core (couples + unmockable);
LangChain-style framework (heavy, hides the tool loop we want to test explicitly).

## R6. query_gl_detail tool

**Decision**: `tools.py` defines the JSON tool schema (inputs: `reporting_line`, `period`,
`scenario`, optional `filters` for project/counterparty/label) and a Python implementation bound
to a `Repository`. It resolves `reporting_line → gl_accounts` via the Block 1 COA config, selects
the matching scenario/period transactions, and returns `GLEvidenceRow`s (account, amount, date,
project, counterparty, labels, txn id). Read-only; no mutation path exists.

**Rationale**: FR-001/002, Principle VI. Binding to the Block 1 `Repository` keeps GL access
source-agnostic; the tool is the agent's only window into detail.

**Alternatives considered**: Giving the model raw repository access (violates the port boundary);
returning DataFrames (leaks pandas into the tool contract).

## R7. Structured output for Question / Draft

**Decision**: The model returns its final answer via a forced tool call
(`emit_investigation`) whose arguments validate against a Pydantic model carrying: `status`
(`question`|`draft`), the hypothesis (or null), the narrative text **with figure tokens**, the
cited evidence row ids, and any aggregate specs. `commentary.py` then renders tokens and assembles
the public `Question`/`Draft`. Free-form text is never parsed for these objects.

**Rationale**: STRUCTURED OUTLET requirement. Tool-call arguments give a typed, validated channel;
Pydantic rejects malformed shapes before any rendering.

**Alternatives considered**: JSON-in-text parsing (brittle); regex extraction (rejected).

## R8. Audit log

**Decision**: `audit.py` appends one JSON object per LLM call to a `.jsonl` file:
`{ts, model, request, response, tool_calls}`. `ts` is supplied by the caller (passed in, not read
from the clock inside the core) so tests are deterministic; the real shell stamps wall-clock time.
A redaction step guarantees the API key is never serialized. Each emitted Question/Draft stores
the log entry id(s) (`LLMLogRef`) that produced it.

**Rationale**: FR-017/018, Principle II + VIII (key never logged). Caller-supplied timestamp keeps
the core pure and the tests deterministic.

**Alternatives considered**: Logging inside the adapter only (loses the per-output linkage); free
text logs (not machine-auditable).

## R9. Agent settings (config-driven)

**Decision**: `AgentSettings` (Pydantic) holds `model_id`, `temperature` (default `0`),
`max_tool_calls_per_variance` (default e.g. `4`), and a `question_policy` controlling the
self-explanatory-vs-question decision (e.g. `dominant_share_threshold`: if one evidence row is
≥X% of the absolute variance, treat as self-explanatory → Draft; else Question). Loaded from
`config/agent_settings.csv`. No model name in code.

**Rationale**: Principle V. Making the question policy explicit and config-driven makes SC-004
(no redundant questions) testable and tunable without code changes.

**Alternatives considered**: Hardcoding the policy in the prompt (untestable, not config-driven);
letting the model decide freely (non-deterministic, harder to validate).

## R10. Determinism & test strategy

**Decision**: All agent-logic tests inject `FakeLLMProvider` with scripted responses, so the
loop, guard, commentary, and contracts run offline and deterministically. The guard gets a
dedicated adversarial suite (numbers absent from sources, disguised figures, aggregates that
don't recompute). One end-to-end test exercises a real `query_gl_detail` call driven by the fake
provider. No network in the suite.

**Rationale**: DETERMINISM AND TESTING requirement; isolates the only non-deterministic component.

**Alternatives considered**: Recorded real-model fixtures (flaky, network-coupled — rejected for
the core suite; could be an optional, separately-marked live smoke test).

---

## Resolved unknowns summary

| Topic | Resolution |
|-------|-----------|
| Numbers in output | Reference-and-render; model emits tokens, code substitutes values |
| Allowed figures | Verbatim source values + code-computed aggregates (sum/count/min/max) over cited rows |
| Guard | Pure `assert_grounded`; regex extract → Decimal normalize → membership; pre- and post-render |
| LLM port | One-method `LLMProvider` Protocol; OpenRouter adapter (only httpx/key site); FakeLLMProvider |
| GL tool | `query_gl_detail` bound to Block 1 Repository; resolves line→accounts; read-only |
| Structured output | Forced `emit_investigation` tool call → Pydantic; never parse free text |
| Audit | JSON-lines per call; caller-supplied ts; key redacted; output links to log id |
| Config | `AgentSettings`: model, temperature, max tool calls, question policy |
| Tests | FakeLLMProvider everywhere; guard adversarial suite; offline |
