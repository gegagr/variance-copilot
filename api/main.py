"""FastAPI app + composition root for Block 4.

Wires the fixture Repository, engine, agent, and SqliteReviewStore via FastAPI dependencies
(api/deps.py). Routes are thin; workflow lives in api/services. CORS enabled for the configured
frontend origin. OpenAPI/Swagger at /docs.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.api_settings import load_api_settings
from api.routes import investigations, pnl, review


def create_app() -> FastAPI:
    settings = load_api_settings()
    app = FastAPI(title="Variance Copilot — Review API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.cors_origin],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Include review.py first so literal /review/progress, /review/accepted are matched
    # before the parameterized /review/{flag_id}.
    app.include_router(review.router)
    app.include_router(investigations.router)
    app.include_router(pnl.router)
    return app


app = create_app()
