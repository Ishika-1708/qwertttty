"""FastAPI application factory.  Run:  uvicorn module2.main:app --reload"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .api.v1_routes import v1_router
from .config import CALCULATION_VERSION, AnalyticsConfig
from .providers import DatasetProvider, FileDatasetProvider


def create_app(provider: Optional[DatasetProvider] = None, config: Optional[AnalyticsConfig] = None) -> FastAPI:
    app = FastAPI(
        title="Wind Forecast Evaluation - Module 2 Analytics",
        version=CALCULATION_VERSION,
        description="Statistical evaluation of published wind forecasts against actual generation. "
                    "All metrics are computed here; the dashboard must not recompute them.",
    )
    app.state.provider = provider or FileDatasetProvider()
    app.state.config = config or AnalyticsConfig(
        aggregation_timezone=os.environ.get("AGGREGATION_TIMEZONE", "UTC"),
        display_timezone=os.environ.get("DISPLAY_TIMEZONE", "Europe/London"),
    )
    app.state.service = None
    default_origins = (
        "http://localhost:5173,http://localhost:4173,http://localhost:3000,http://localhost:8080,"
        "http://127.0.0.1:5173,http://127.0.0.1:4173,http://127.0.0.1:3000,http://127.0.0.1:8080"
    )
    origins = [o.strip() for o in os.environ.get("DASHBOARD_ORIGINS", default_origins).split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins if "*" not in origins else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    app.include_router(v1_router)

    @app.get("/health", tags=["meta"])
    def health():
        now = datetime.now(timezone.utc).isoformat()
        return {
            "status": "ok",
            "version": CALCULATION_VERSION,
            "calculation_version": CALCULATION_VERSION,
            "checked_at": now,
            "last_successful_ingest_at": now,
        }

    return app


app = create_app()
