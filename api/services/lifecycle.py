"""The review lifecycle state machine (pure; the single source of truth for transitions).

`transition(status, action)` returns the new status for a valid (status, action) pair and
raises `InvalidTransition` otherwise. The internal resolution of an investigation
(investigating → awaiting_controller | drafted | detected) is driven by the agent result in the
service, NOT by a controller action, so it is not part of this table.
"""

from __future__ import annotations

from data.review_store import ReviewActionType, ReviewStatus

S = ReviewStatus
A = ReviewActionType


class InvalidTransition(Exception):
    """Raised when a (status, action) pair is not a permitted transition."""


# (current status, action) -> new status
TRANSITIONS: dict[tuple[ReviewStatus, ReviewActionType], ReviewStatus] = {
    (S.DETECTED, A.INVESTIGATE): S.INVESTIGATING,
    (S.DRAFTED, A.INVESTIGATE): S.INVESTIGATING,      # re-run: discards prior draft (service resets provenance)
    (S.AWAITING_CONTROLLER, A.ANSWER): S.DRAFTED,
    (S.DRAFTED, A.ACCEPT): S.ACCEPTED,
    (S.DRAFTED, A.EDIT): S.DRAFTED,
    (S.ACCEPTED, A.EDIT): S.DRAFTED,                  # editing accepted reverts to drafted (re-accept required)
    (S.DETECTED, A.DISMISS): S.DISMISSED,
    (S.AWAITING_CONTROLLER, A.DISMISS): S.DISMISSED,
    (S.DRAFTED, A.DISMISS): S.DISMISSED,
    (S.ACCEPTED, A.DISMISS): S.DISMISSED,
    # A failed investigation is actionable: it can be re-run or dismissed.
    (S.FAILED, A.INVESTIGATE): S.INVESTIGATING,
    (S.FAILED, A.DISMISS): S.DISMISSED,
}


def transition(status: ReviewStatus, action: ReviewActionType) -> ReviewStatus:
    try:
        return TRANSITIONS[(status, action)]
    except KeyError:
        raise InvalidTransition(f"cannot {action.value} from {status.value}")
