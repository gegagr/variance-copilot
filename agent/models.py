"""Output contracts and supporting models for the AI investigation layer (Block 3).

All money/ratio values are ``Decimal`` (serialized as strings in JSON, Pydantic v2
default). The three public contracts — InvestigationRecord, Question, Draft — carry an
explicit ``schema_version`` and embed immutable GL-evidence snapshots, mirroring Block 1's
FlaggedVariance approach.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel

from engine.models import FlaggedVariance


class RecordStatus(str, Enum):
    QUESTION = "question"
    DRAFT = "draft"


class AggregateOp(str, Enum):
    SUM = "sum"
    COUNT = "count"
    MIN = "min"
    MAX = "max"


class FigureSource(str, Enum):
    BLOCK1 = "block1"
    GL = "gl"
    AGGREGATE = "aggregate"


# --------------------------------------------------------------------------- #
# GL evidence
# --------------------------------------------------------------------------- #
class GLEvidenceRow(BaseModel):
    transaction_id: str
    gl_account: str
    amount: Decimal
    period: int
    scenario: str
    date: str
    project: Optional[str] = None
    counterparty: Optional[str] = None
    labels: list[str] = []


class GLQuery(BaseModel):
    """A read-only request for the GL rows behind a reporting line.

    Two equivalent ways to select the slice; ``query_gl_detail`` resolves either,
    mirroring exactly how the engine's aggregation resolves the same dimensions:

    * **Explicit form** — concrete data-column values: ``period`` (1..12) and
      ``scenario`` (``current_year``/``prior_year``/``budget``).
    * **Flag form** — the variance's own dimensions: ``time_cut`` (e.g. ``current_month``)
      and ``scenario_pair`` (e.g. ``current_vs_prior_year``), resolved against
      ``current_period``. The *current* side of every comparison is current-year actuals,
      so a bare ``scenario_pair`` resolves to ``scenario == current_year`` — never a
      literal scenario named after the pair.
    """

    reporting_line: str
    # Explicit form (concrete data columns).
    period: Optional[int] = None
    scenario: Optional[str] = None
    # Flag form (resolved deterministically, mirroring the engine).
    time_cut: Optional[str] = None
    scenario_pair: Optional[str] = None
    current_period: Optional[int] = None
    filters: Optional[dict] = None


class GLQueryResult(BaseModel):
    query: GLQuery
    rows: list[GLEvidenceRow]


# --------------------------------------------------------------------------- #
# Figure references & rendering (reference-and-render)
# --------------------------------------------------------------------------- #
class AggregateSpec(BaseModel):
    agg_id: str
    op: AggregateOp
    row_ids: list[str]


class RenderedFigure(BaseModel):
    token: str
    source: FigureSource
    value: Decimal
    origin: str


# --------------------------------------------------------------------------- #
# Investigation pieces
# --------------------------------------------------------------------------- #
class Hypothesis(BaseModel):
    text: Optional[str] = None           # None => no hypothesis (sparse evidence)
    evidence_row_ids: list[str] = []


class ControllerInput(BaseModel):
    input_id: str
    flag_id: str
    text: str
    accepted_hypothesis: bool = True


class DraftProvenance(BaseModel):
    flag_id: str
    evidence_row_ids: list[str]
    controller_input_id: Optional[str] = None


# --------------------------------------------------------------------------- #
# The structured payload the model emits (validated; never free-text parsed)
# --------------------------------------------------------------------------- #
class EmitPayload(BaseModel):
    """Arguments of the forced ``emit_investigation`` tool call."""

    status: RecordStatus
    hypothesis_text: Optional[str] = None
    hypothesis_row_ids: list[str] = []
    narrative: str                        # contains {{fig:...}} tokens, NO raw digits
    cited_row_ids: list[str] = []
    aggregates: list[AggregateSpec] = []


# --------------------------------------------------------------------------- #
# Public contracts (versioned)
# --------------------------------------------------------------------------- #
class Question(BaseModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    question_id: str
    flag_id: str
    text: str
    hypothesis: Hypothesis
    evidence: list[GLEvidenceRow]
    rendered_figures: list[RenderedFigure]
    llm_log_refs: list[str]


class Draft(BaseModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    draft_id: str
    flag_id: str
    commentary: str
    evidence: list[GLEvidenceRow]
    rendered_figures: list[RenderedFigure]
    controller_input: Optional[ControllerInput] = None
    provenance: DraftProvenance
    llm_log_refs: list[str]
    is_proposal: Literal[True] = True


class InvestigationRecord(BaseModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    flag_id: str
    variance: FlaggedVariance
    status: RecordStatus
    evidence: list[GLEvidenceRow]
    hypothesis: Hypothesis
    question: Optional[Question] = None
    draft: Optional[Draft] = None
    llm_log_refs: list[str]
