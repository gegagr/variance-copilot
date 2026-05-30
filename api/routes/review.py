"""Thin routes: accept / edit / dismiss; history; progress; accepted commentary."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from data.review_store import ReviewAction
from api.deps import get_now, get_service
from api.schemas import AcceptedCommentaryItem, EditRequest, ReviewItemView, ReviewProgressView
from api.services.lifecycle import InvalidTransition
from api.services.review_service import NotFound, ReviewService

router = APIRouter(tags=["review"])


# Literal routes are declared (and included) before /review/{flag_id} to avoid path capture.
@router.get("/review/progress", response_model=ReviewProgressView)
def progress(service: Annotated[ReviewService, Depends(get_service)]) -> ReviewProgressView:
    service.get_flags(service.config.settings.current_period)
    return service.progress()


@router.get("/review/accepted", response_model=list[AcceptedCommentaryItem])
def accepted(service: Annotated[ReviewService, Depends(get_service)]) -> list[AcceptedCommentaryItem]:
    return service.accepted_commentary()


@router.get("/review/{flag_id}/history", response_model=list[ReviewAction])
def history(flag_id: str, service: Annotated[ReviewService, Depends(get_service)]) -> list[ReviewAction]:
    try:
        return service.history(flag_id)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))


def _act(fn, flag_id, service, now):
    try:
        return ReviewItemView.of(fn(flag_id, now=now))
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/review/{flag_id}/accept", response_model=ReviewItemView)
def accept(flag_id: str, service: Annotated[ReviewService, Depends(get_service)],
           now: Annotated[str, Depends(get_now)]) -> ReviewItemView:
    return _act(service.accept, flag_id, service, now)


@router.post("/review/{flag_id}/dismiss", response_model=ReviewItemView)
def dismiss(flag_id: str, service: Annotated[ReviewService, Depends(get_service)],
            now: Annotated[str, Depends(get_now)]) -> ReviewItemView:
    return _act(service.dismiss, flag_id, service, now)


@router.post("/review/{flag_id}/edit", response_model=ReviewItemView)
def edit(flag_id: str, body: EditRequest, service: Annotated[ReviewService, Depends(get_service)],
         now: Annotated[str, Depends(get_now)]) -> ReviewItemView:
    try:
        return ReviewItemView.of(service.edit(flag_id, body.edited_text, now=now))
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
