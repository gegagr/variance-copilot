"""Foundational (TEST-FIRST): the review lifecycle state machine.

Every valid (status, action) transition succeeds; every invalid one is rejected.
"""

from __future__ import annotations

import pytest

from data.review_store import RESOLVED, ReviewActionType as A, ReviewStatus as S


VALID = {
    (S.DETECTED, A.INVESTIGATE): S.INVESTIGATING,
    (S.DRAFTED, A.INVESTIGATE): S.INVESTIGATING,
    (S.AWAITING_CONTROLLER, A.ANSWER): S.DRAFTED,
    (S.DRAFTED, A.ACCEPT): S.ACCEPTED,
    (S.DRAFTED, A.EDIT): S.DRAFTED,
    (S.ACCEPTED, A.EDIT): S.DRAFTED,
    (S.DETECTED, A.DISMISS): S.DISMISSED,
    (S.AWAITING_CONTROLLER, A.DISMISS): S.DISMISSED,
    (S.DRAFTED, A.DISMISS): S.DISMISSED,
    (S.ACCEPTED, A.DISMISS): S.DISMISSED,
}


def test_every_valid_transition_succeeds():
    from api.services.lifecycle import transition
    for (status, action), expected in VALID.items():
        assert transition(status, action) is expected


def test_every_invalid_transition_is_rejected():
    from api.services.lifecycle import InvalidTransition, transition
    for status in S:
        for action in A:
            if (status, action) in VALID:
                continue
            with pytest.raises(InvalidTransition):
                transition(status, action)


def test_specific_rejections():
    from api.services.lifecycle import InvalidTransition, transition
    # accept while awaiting the controller -> rejected
    with pytest.raises(InvalidTransition):
        transition(S.AWAITING_CONTROLLER, A.ACCEPT)
    # investigate while accepted -> rejected
    with pytest.raises(InvalidTransition):
        transition(S.ACCEPTED, A.INVESTIGATE)
    # answer while drafted -> rejected
    with pytest.raises(InvalidTransition):
        transition(S.DRAFTED, A.ANSWER)


def test_edit_on_accepted_reverts_to_drafted():
    from api.services.lifecycle import transition
    assert transition(S.ACCEPTED, A.EDIT) is S.DRAFTED


def test_resolved_set():
    assert RESOLVED == {S.ACCEPTED, S.DISMISSED}
