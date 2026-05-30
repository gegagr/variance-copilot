"""Thin routes: serve the engine P&L and flagged variances (pass-through, no recompute)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from engine.models import FlaggedVariance, PnLResult, TimeCut
from api.deps import get_service
from api.services.review_service import ReviewService

router = APIRouter(tags=["pnl"])


@router.get("/pnl", response_model=PnLResult)
def get_pnl(
    service: Annotated[ReviewService, Depends(get_service)],
    current_period: int = Query(ge=1, le=12),
    time_cut: TimeCut = Query(default=TimeCut.YTD),
) -> PnLResult:
    return service.get_pnl(current_period, time_cut)


@router.get("/variances", response_model=list[FlaggedVariance])
def get_variances(
    service: Annotated[ReviewService, Depends(get_service)],
    current_period: int = Query(ge=1, le=12),
) -> list[FlaggedVariance]:
    return service.get_flags(current_period)
