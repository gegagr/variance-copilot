"""FastAPI dependency providers (composition seam). Tests override get_provider/get_review_store."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import Depends

from config.agent_settings import load_agent_settings
from config.api_settings import APISettings, load_api_settings
from config.loader import load_config
from data.fixture_repository import FixtureRepository
from data.gl_detail_repository import GLDetailRepository
from data.review_store import ReviewStore
from data.sqlite_review_store import SqliteReviewStore
from agent.provider import LLMProvider, OpenRouterProvider
from api.services.review_service import ReviewService

CONFIG_DIR = Path("config")
SAMPLE_DIR = Path("sample")


def get_api_settings() -> APISettings:
    return load_api_settings()


def get_provider() -> LLMProvider:
    return OpenRouterProvider()


def get_review_store(settings: Annotated[APISettings, Depends(get_api_settings)]) -> ReviewStore:
    return SqliteReviewStore(settings.sqlite_path)


def get_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_service(
    settings: Annotated[APISettings, Depends(get_api_settings)],
    provider: Annotated[LLMProvider, Depends(get_provider)],
    store: Annotated[ReviewStore, Depends(get_review_store)],
) -> ReviewService:
    config = load_config(CONFIG_DIR, current_period=settings.current_period)
    return ReviewService(
        repo=FixtureRepository(SAMPLE_DIR),
        gl_repo=GLDetailRepository(SAMPLE_DIR),
        config=config,
        config_dir=CONFIG_DIR,
        agent_settings=load_agent_settings(CONFIG_DIR),
        provider=provider,
        store=store,
        controller_id=settings.controller_id,
    )
