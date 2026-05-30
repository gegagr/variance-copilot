"""API request/response DTOs. Reuse Block 1/3 contract models verbatim — never re-model a figure."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from agent.models import ControllerInput, Draft, DraftProvenance, InvestigationRecord
from data.review_store import ReviewItem, ReviewStatus


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
    updated_at: str = ""

    @classmethod
    def of(cls, item: ReviewItem) -> "ReviewItemView":
        return cls(
            flag_id=item.flag_id, reporting_line=item.reporting_line, status=item.status,
            record=item.record, original_draft=item.original_draft,
            controller_answer=item.controller_answer, edited_text=item.edited_text,
            updated_at=item.updated_at,
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
