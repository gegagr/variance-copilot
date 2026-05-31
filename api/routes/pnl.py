"""Thin routes: serve the engine P&L and flagged variances (pass-through, no recompute)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from engine.models import FlaggedVariance, PnLResult, TimeCut
from api.deps import get_service
from api.schemas import FlaggedVarianceView, PnLResultView
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


# --- Display-string view endpoints (consumed by the UI; raw endpoints above stay byte-pure) ---
@router.get("/pnl/view", response_model=PnLResultView)
def get_pnl_view(
    service: Annotated[ReviewService, Depends(get_service)],
    current_period: int = Query(ge=1, le=12),
    time_cut: TimeCut = Query(default=TimeCut.YTD),
) -> PnLResultView:
    return service.get_pnl_view(current_period, time_cut)


@router.get("/variances/view", response_model=list[FlaggedVarianceView])
def get_variances_view(
    service: Annotated[ReviewService, Depends(get_service)],
    current_period: int = Query(ge=1, le=12),
) -> list[FlaggedVarianceView]:
    return service.get_flags_view(current_period)
