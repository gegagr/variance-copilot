"""API request/response DTOs. Reuse Block 1/3 contract models verbatim — never re-model a figure."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from agent.models import ControllerInput, Draft, DraftProvenance, InvestigationRecord
from data.review_store import ReviewItem, ReviewStatus
from engine import format as fmt
from engine.models import FlaggedVariance, LineType, PnLResult, ValueKind


class AnswerRequest(BaseModel):
    text: str
    accepted_hypothesis: bool = True


class EditRequest(BaseModel):
    edited_text: str


class ReviewItemView(BaseModel):
    flag_id: str
    reporting_line: str
    status: ReviewStatus
    record: Optional[InvestigationRecord] = None
    original_draft: Optional[Draft] = None
    controller_answer: Optional[ControllerInput] = None
    edited_text: Optional[str] = None
    error: Optional[str] = None
    updated_at: str = ""

    @classmethod
    def of(cls, item: ReviewItem) -> "ReviewItemView":
        return cls(
            flag_id=item.flag_id, reporting_line=item.reporting_line, status=item.status,
            record=item.record, original_draft=item.original_draft,
            controller_answer=item.controller_answer, edited_text=item.edited_text,
            error=item.error, updated_at=item.updated_at,
        )


class ReviewProgressView(BaseModel):
    total: int
    resolved: int
    by_status: dict[str, int]


class AcceptedCommentaryItem(BaseModel):
    flag_id: str
    reporting_line: str
    order: int
    text: str
    is_edited: bool
    provenance: DraftProvenance


# --------------------------------------------------------------------------- #
# Display-string view DTOs (Block 5 dependency) — figures formatted by deterministic Python.
# Served from /pnl/view and /variances/view; the raw /pnl and /variances stay byte-pure.
# --------------------------------------------------------------------------- #
class PnlCellView(BaseModel):
    reporting_line: str
    scenario: str
    time_cut: str
    value: str          # raw decimal string (provenance)
    display: str        # Python-formatted display string
    value_kind: str
    is_margin: bool


class PnLLineView(BaseModel):
    reporting_line: str
    order: int
    line_type: str
    cells: list[PnlCellView]


class PnLResultView(BaseModel):
    lines: list[PnLLineView]
    reporting_currency: str
    current_period: int


class FlaggedVarianceView(FlaggedVariance):
    """The Block 1 flag (all fields) PLUS Python-formatted display strings."""

    current_display: str
    comparator_display: str
    abs_display: str | None = None
    pct_display: str | None = None
    pp_display: str | None = None


def _cell_display(value, value_kind: ValueKind, is_margin: bool) -> str:
    if value_kind is ValueKind.NOT_MEANINGFUL:
        return fmt.not_meaningful()
    return fmt.percent(value) if is_margin else fmt.money(value)


def to_pnl_view(result: PnLResult) -> PnLResultView:
    lines = [
        PnLLineView(
            reporting_line=line.reporting_line, order=line.order, line_type=line.line_type.value,
            cells=[
                PnlCellView(
                    reporting_line=c.reporting_line, scenario=c.scenario.value,
                    time_cut=c.time_cut.value, value=str(c.value),
                    display=_cell_display(c.value, c.value_kind, c.is_margin),
                    value_kind=c.value_kind.value, is_margin=c.is_margin,
                )
                for c in line.cells
            ],
        )
        for line in result.lines
    ]
    return PnLResultView(lines=lines, reporting_currency=result.reporting_currency,
                         current_period=result.current_period)


def to_flag_view(flag: FlaggedVariance) -> FlaggedVarianceView:
    is_margin = flag.line_type is LineType.MARGIN
    cur = fmt.percent(flag.current_value) if is_margin else fmt.money(flag.current_value)
    cmp = fmt.percent(flag.comparator_value) if is_margin else fmt.money(flag.comparator_value)
    return FlaggedVarianceView(
        **flag.model_dump(),
        current_display=cur,
        comparator_display=cmp,
        abs_display=(fmt.money(flag.abs_variance) if flag.abs_variance is not None else None),
        pct_display=(fmt.percent(flag.pct_variance) if flag.pct_variance is not None else None),
        pp_display=(fmt.points(flag.pp_variance) if flag.pp_variance is not None else None),
    )
