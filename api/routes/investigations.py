"""Thin routes: run/get investigations; submit a controller answer. No workflow logic here."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_now, get_service
from api.schemas import AnswerRequest, ReviewItemView
from api.services.lifecycle import InvalidTransition
from api.services.review_service import NotFound, ReviewService

router = APIRouter(tags=["investigations"])


@router.get("/review", response_model=list[ReviewItemView])
def list_review(service: Annotated[ReviewService, Depends(get_service)]) -> list[ReviewItemView]:
    # Ensure items exist for the session's flags, then list them.
    service.get_flags(service.config.settings.current_period)
    return [ReviewItemView.of(it) for it in service.store.list_all()]


@router.get("/review/{flag_id}", response_model=ReviewItemView)
def get_review_item(flag_id: str, service: Annotated[ReviewService, Depends(get_service)]) -> ReviewItemView:
    item = service.store.get(flag_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"unknown flag {flag_id}")
    return ReviewItemView.of(item)


@router.post("/review/{flag_id}/investigate", response_model=ReviewItemView)
def investigate(flag_id: str, service: Annotated[ReviewService, Depends(get_service)],
                now: Annotated[str, Depends(get_now)]) -> ReviewItemView:
    try:
        return ReviewItemView.of(service.investigate(flag_id, now=now))
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/review/{flag_id}/answer", response_model=ReviewItemView)
def answer(flag_id: str, body: AnswerRequest, service: Annotated[ReviewService, Depends(get_service)],
           now: Annotated[str, Depends(get_now)]) -> ReviewItemView:
    try:
        return ReviewItemView.of(
            service.answer(flag_id, body.text, body.accepted_hypothesis, now=now)
        )
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
