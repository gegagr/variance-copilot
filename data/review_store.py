"""Review-state domain models, the ReviewStore port, and an in-memory test double.

Persists the controller's review workflow per flagged variance. Block 3 contract models
(`InvestigationRecord`, `Draft`, `ControllerInput`) are embedded as immutable snapshots — the
store never decomposes a figure into numeric columns, so it cannot alter one.
"""

from __future__ import annotations

import copy
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional

from pydantic import BaseModel

from agent.models import ControllerInput, Draft, InvestigationRecord


class ReviewStatus(str, Enum):
    DETECTED = "detected"
    INVESTIGATING = "investigating"
    AWAITING_CONTROLLER = "awaiting_controller"
    DRAFTED = "drafted"
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"
    FAILED = "failed"  # investigation produced no grounded record; carries an error reason


RESOLVED = {ReviewStatus.ACCEPTED, ReviewStatus.DISMISSED}

# Canonical identifier is `awaiting_controller` (underscore). The hyphenated
# "awaiting-controller" appears only in prose; the enum value is authoritative.


class ReviewActionType(str, Enum):
    INVESTIGATE = "investigate"
    ANSWER = "answer"
    ACCEPT = "accept"
    EDIT = "edit"
    DISMISS = "dismiss"


class ReviewItem(BaseModel):
    flag_id: str
    current_period: int = 0  # the as-of month this item belongs to; part of its identity
    reporting_line: str
    status: ReviewStatus = ReviewStatus.DETECTED
    record: Optional[InvestigationRecord] = None
    original_draft: Optional[Draft] = None
    controller_answer: Optional[ControllerInput] = None
    edited_text: Optional[str] = None
    error: Optional[str] = None  # failure reason when status == FAILED
    created_at: str = ""
    updated_at: str = ""


class ReviewAction(BaseModel):
    action_id: str
    flag_id: str
    current_period: int = 0  # the as-of month whose item changed
    action: ReviewActionType
    actor: str
    ts: str
    from_status: ReviewStatus
    to_status: ReviewStatus
    payload: Optional[dict] = None


class ReviewStore(ABC):
    """Durable store for review items + their action history (Constitution Principle VI).

    Items are identified by ``(current_period, flag_id)`` so each as-of month owns an independent
    review queue and lifecycle state. ``upsert`` and ``append_action`` read the period from the
    model; reads pass it explicitly.
    """

    @abstractmethod
    def get(self, current_period: int, flag_id: str) -> Optional[ReviewItem]: ...

    @abstractmethod
    def upsert(self, item: ReviewItem) -> None: ...

    @abstractmethod
    def list_all(self, current_period: int) -> list[ReviewItem]: ...

    @abstractmethod
    def append_action(self, action: ReviewAction) -> None: ...

    @abstractmethod
    def actions_for(self, current_period: int, flag_id: str) -> list[ReviewAction]: ...


class InMemoryReviewStore(ReviewStore):
    """Test double satisfying the same port (proves the service depends on the abstraction)."""

    def __init__(self) -> None:
        self._items: dict[tuple[int, str], ReviewItem] = {}
        self._actions: list[ReviewAction] = []

    def get(self, current_period: int, flag_id: str) -> Optional[ReviewItem]:
        item = self._items.get((current_period, flag_id))
        return item.model_copy(deep=True) if item else None

    def upsert(self, item: ReviewItem) -> None:
        self._items[(item.current_period, item.flag_id)] = item.model_copy(deep=True)

    def list_all(self, current_period: int) -> list[ReviewItem]:
        return [i.model_copy(deep=True) for (p, _), i in self._items.items() if p == current_period]

    def append_action(self, action: ReviewAction) -> None:
        self._actions.append(copy.deepcopy(action))

    def actions_for(self, current_period: int, flag_id: str) -> list[ReviewAction]:
        return [a for a in self._actions if a.current_period == current_period and a.flag_id == flag_id]
