"""Commentary rendering — code substitutes every figure (the model never types a digit).

Resolves `{{fig:...}}` tokens in the model's narrative to actual `Decimal` values drawn from
the allowed set (Block 1 figures + GL amounts + code-computed aggregates), formats them, and
builds the `Question` / `Draft` together with the `rendered_figures` audit list and the
`AllowedValues` the guard validates against.
"""

from __future__ import annotations

import re
from decimal import Decimal

from engine.models import LineType
from agent.guards import AllowedValues
from agent.models import (
    AggregateOp,
    ControllerInput,
    Draft,
    DraftProvenance,
    EmitPayload,
    FigureSource,
    GLEvidenceRow,
    Hypothesis,
    Question,
    RenderedFigure,
)

FIG_TOKEN_RE = re.compile(r"\{\{fig:([^}]+)\}\}")

# Arithmetic expressed BETWEEN two figure tokens (e.g. "{{fig:a}} - {{fig:b}}"). The model may
# never compute: it references existing figures only. A computed total must be an `agg:` aggregate.
ARITHMETIC_BETWEEN_FIGURES_RE = re.compile(r"\}\}\s*[-+*/×÷=]\s*\{\{")

_FLAG_DOMAIN = {
    "abs_variance": "money",
    "abs_threshold": "money",
    "pct_variance": "ratio",
    "pp_variance": "ratio",
    "pct_threshold": "ratio",
    "pp_threshold": "ratio",
}

# The CLOSED set of flag figure fields a {{fig:flag.<field>}} token may reference. Anything else
# (e.g. 'direction', 'reporting_line') is not a figure and is rejected.
VALID_FLAG_FIGURE_FIELDS: tuple[str, ...] = ("current_value", "comparator_value", *_FLAG_DOMAIN)


class RenderError(ValueError):
    """Raised when a figure token cannot be resolved (triggers retry / fail-safe upstream)."""


def _flag_figure(flag, field: str) -> tuple[Decimal, str]:
    """Return (value, domain) for a flag figure field."""
    if field not in VALID_FLAG_FIGURE_FIELDS:
        raise RenderError(
            f"unknown flag figure field {field!r}; a flag figure must be one of: "
            f"{', '.join(VALID_FLAG_FIGURE_FIELDS)}"
        )
    is_margin = flag.line_type is LineType.MARGIN
    if field in ("current_value", "comparator_value"):
        domain = "ratio" if is_margin else "money"
    else:
        domain = _FLAG_DOMAIN[field]
    value = getattr(flag, field, None)
    if value is None:
        raise RenderError(f"flag figure {field!r} is not available for this variance")
    return Decimal(value), domain


def _compute_aggregate(spec, rows_by_id: dict[str, GLEvidenceRow]) -> Decimal:
    try:
        amounts = [rows_by_id[rid].amount for rid in spec.row_ids]
    except KeyError as exc:
        raise RenderError(f"aggregate {spec.agg_id} cites unknown row {exc}") from exc
    if not amounts and spec.op is not AggregateOp.COUNT:
        raise RenderError(f"aggregate {spec.agg_id} has no rows")
    if spec.op is AggregateOp.SUM:
        return sum(amounts, Decimal(0))
    if spec.op is AggregateOp.COUNT:
        return Decimal(len(spec.row_ids))
    if spec.op is AggregateOp.MIN:
        return min(amounts)
    if spec.op is AggregateOp.MAX:
        return max(amounts)
    raise RenderError(f"unknown aggregate op: {spec.op}")


def _fmt_money(v: Decimal) -> str:
    return f"€{v.quantize(Decimal('0.01')):,.2f}"


def _fmt_ratio(v: Decimal) -> str:
    pct = (v * 100).quantize(Decimal("0.0001"))
    s = format(pct, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return f"{s}%"


def build_allowed(flag, evidence: list[GLEvidenceRow], agg_values: dict[str, Decimal]) -> AllowedValues:
    allowed = AllowedValues()
    is_margin = flag.line_type is LineType.MARGIN
    money_fields = ["abs_variance", "abs_threshold"] + (
        [] if is_margin else ["current_value", "comparator_value"]
    )
    ratio_fields = ["pct_variance", "pp_variance", "pct_threshold", "pp_threshold"] + (
        ["current_value", "comparator_value"] if is_margin else []
    )
    for f in money_fields:
        v = getattr(flag, f, None)
        if v is not None:
            allowed.add_money(Decimal(v))
    for f in ratio_fields:
        v = getattr(flag, f, None)
        if v is not None:
            allowed.add_ratio(Decimal(v))
    for row in evidence:
        allowed.add_money(row.amount)
    for v in agg_values.values():
        allowed.add_money(v)
    return allowed


def render_output(payload: EmitPayload, evidence: list[GLEvidenceRow], flag):
    """Resolve figure tokens → (rendered_text, rendered_figures, allowed)."""
    if ARITHMETIC_BETWEEN_FIGURES_RE.search(payload.narrative):
        raise RenderError(
            "narrative expresses arithmetic between figures (e.g. '{{fig:a}} - {{fig:b}}'); "
            "never compute — reference existing figures only, and for a total define an aggregate "
            "(op over row_ids) and cite it as {{fig:agg:<id>}}"
        )
    rows_by_id = {r.transaction_id: r for r in evidence}
    agg_specs = {a.agg_id: a for a in payload.aggregates}
    agg_values = {a.agg_id: _compute_aggregate(a, rows_by_id) for a in payload.aggregates}
    allowed = build_allowed(flag, evidence, agg_values)

    figures: list[RenderedFigure] = []

    def resolve(match: re.Match) -> str:
        token = match.group(0)
        inner = match.group(1)
        if inner.startswith("flag."):
            field = inner[len("flag."):]
            value, domain = _flag_figure(flag, field)
            source, origin = FigureSource.BLOCK1, field
        elif inner.startswith("gl:"):
            ref = inner[len("gl:"):]
            txn_id, _, attr = ref.partition(".")
            if attr != "amount":
                raise RenderError(
                    f"invalid GL token {token}: a GL figure must be 'fig:gl:<txn_id>.amount' "
                    "(only the .amount of a returned transaction can be cited)"
                )
            if txn_id not in rows_by_id:
                raise RenderError(
                    f"GL token {token} cites unknown transaction {txn_id!r}; cite a transaction id "
                    "returned by query_gl_detail"
                )
            value, domain = rows_by_id[txn_id].amount, "money"
            source, origin = FigureSource.GL, txn_id
        elif inner.startswith("agg:"):
            agg_id = inner[len("agg:"):]
            if agg_id not in agg_values:
                raise RenderError(
                    f"aggregate token {token} references undefined aggregate {agg_id!r}; define it "
                    "in `aggregates` as {agg_id, op, row_ids}"
                )
            value, domain = agg_values[agg_id], "money"
            source, origin = FigureSource.AGGREGATE, agg_id
        else:
            raise RenderError(
                f"unrecognised figure token {token}; valid forms: {{{{fig:flag.<field>}}}}, "
                "{{fig:gl:<txn_id>.amount}}, {{fig:agg:<id>}}"
            )

        figures.append(RenderedFigure(token=token, source=source, value=value, origin=origin))
        return _fmt_money(value) if domain == "money" else _fmt_ratio(value)

    text = FIG_TOKEN_RE.sub(resolve, payload.narrative)
    return text, figures, allowed


def build_question(flag, payload: EmitPayload, evidence, text, figures, log_refs) -> Question:
    return Question(
        question_id=f"{flag.flag_id}:question",
        flag_id=flag.flag_id,
        text=text,
        hypothesis=Hypothesis(text=payload.hypothesis_text, evidence_row_ids=payload.hypothesis_row_ids),
        evidence=evidence,
        rendered_figures=figures,
        llm_log_refs=log_refs,
    )


def build_draft(flag, payload: EmitPayload, evidence, text, figures, log_refs,
                controller_input: ControllerInput | None) -> Draft:
    return Draft(
        draft_id=f"{flag.flag_id}:draft",
        flag_id=flag.flag_id,
        commentary=text,
        evidence=evidence,
        rendered_figures=figures,
        controller_input=controller_input,
        provenance=DraftProvenance(
            flag_id=flag.flag_id,
            evidence_row_ids=[r.transaction_id for r in evidence],
            controller_input_id=controller_input.input_id if controller_input else None,
        ),
        llm_log_refs=log_refs,
    )
