"""Thin routes: accept / edit / dismiss; history; progress; accepted commentary."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from data.review_store import ReviewAction
from api.deps import get_now, get_service
from api.schemas import AcceptedCommentaryItem, EditRequest, ReviewItemView, ReviewProgressView
from api.services.lifecycle import InvalidTransition
from api.services.review_service import NotFound, ReviewService

router = APIRouter(tags=["review"])


# Literal routes are declared (and included) before /review/{flag_id} to avoid path capture.
@router.get("/review/progress", response_model=ReviewProgressView)
def progress(service: Annotated[ReviewService, Depends(get_service)],
             current_period: int = Query(ge=1, le=12)) -> ReviewProgressView:
    service.get_flags(current_period)
    return service.progress(current_period)


@router.get("/review/accepted", response_model=list[AcceptedCommentaryItem])
def accepted(service: Annotated[ReviewService, Depends(get_service)],
             current_period: int = Query(ge=1, le=12)) -> list[AcceptedCommentaryItem]:
    return service.accepted_commentary(current_period)


@router.get("/review/{flag_id}/history", response_model=list[ReviewAction])
def history(flag_id: str, service: Annotated[ReviewService, Depends(get_service)],
            current_period: int = Query(ge=1, le=12)) -> list[ReviewAction]:
    try:
        return service.history(flag_id, current_period)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))


def _act(fn, flag_id, current_period, now):
    try:
        return ReviewItemView.of(fn(flag_id, current_period, now=now))
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/review/{flag_id}/accept", response_model=ReviewItemView)
def accept(flag_id: str, service: Annotated[ReviewService, Depends(get_service)],
           now: Annotated[str, Depends(get_now)],
           current_period: int = Query(ge=1, le=12)) -> ReviewItemView:
    return _act(service.accept, flag_id, current_period, now)


@router.post("/review/{flag_id}/dismiss", response_model=ReviewItemView)
def dismiss(flag_id: str, service: Annotated[ReviewService, Depends(get_service)],
            now: Annotated[str, Depends(get_now)],
            current_period: int = Query(ge=1, le=12)) -> ReviewItemView:
    return _act(service.dismiss, flag_id, current_period, now)


@router.post("/review/{flag_id}/edit", response_model=ReviewItemView)
def edit(flag_id: str, body: EditRequest, service: Annotated[ReviewService, Depends(get_service)],
         now: Annotated[str, Depends(get_now)],
         current_period: int = Query(ge=1, le=12)) -> ReviewItemView:
    try:
        return ReviewItemView.of(service.edit(flag_id, current_period, body.edited_text, now=now))
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
