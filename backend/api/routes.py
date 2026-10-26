"""Thin HTTP layer. No calculation here: every handler delegates to AnalyticsService."""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from ..contract import SchemaError
from ..providers import DatasetUnavailable
from ..service import AnalyticsService
from . import schemas

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

def _start():
    return Query(None, description="Inclusive first delivery date (YYYY-MM-DD) in the configured aggregation timezone.")


def _end():
    return Query(None, description="Inclusive last delivery date (YYYY-MM-DD) in the configured aggregation timezone.")


def _service(request: Request) -> AnalyticsService:
    """Build (or reuse) a service for the CURRENT Module 1 dataset version."""
    try:
        dataset = request.app.state.provider.get_dataset()
    except DatasetUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    cached = getattr(request.app.state, "service", None)
    if cached is None or cached.dataset.dataset_version != dataset.dataset_version or cached.dataset.dataset_id != dataset.dataset_id:
        cached = AnalyticsService(dataset, request.app.state.config)
        request.app.state.service = cached
    return cached


def _call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except SchemaError as exc:           # upstream (Module 1) contract violation
        raise HTTPException(status_code=502, detail=f"Module 1 contract violation: {exc}")
    except ValueError as exc:            # bad query parameters
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/summary", response_model=schemas.SummaryResponse)
def summary(request: Request, start_date: Optional[date] = _start(), end_date: Optional[date] = _end(),
            include_mape: bool = Query(False, description="Add MAPE (actuals below the configured floor are excluded and counted).")):
    """Headline MAE / RMSE / MBE over the valid matched pairs, plus coverage and traceability."""
    return _call(_service(request).summary, start_date, end_date, include_mape)


@router.get("/intervals", response_model=schemas.IntervalsResponse)
def intervals(request: Request, start_date: Optional[date] = _start(), end_date: Optional[date] = _end(),
              status: str = Query("valid", description="valid | excluded | all"),
              limit: int = Query(1000, ge=1, le=10000), offset: int = Query(0, ge=0)):
    """Interval-level forecast, actual, signed error and absolute error (paginated, ascending time)."""
    return _call(_service(request).intervals, start_date, end_date, status, limit, offset)


@router.get("/daily", response_model=schemas.AggregationResponse)
def daily(request: Request, start_date: Optional[date] = _start(), end_date: Optional[date] = _end(),
          group_by: str = Query("date", description="date | time_of_day"),
          bucket_minutes: int = Query(60, ge=1, le=1440, description="Bucket width for group_by=time_of_day.")):
    """Descriptive MAE/RMSE/MBE by delivery date or by time-of-day bucket, with sample counts."""
    return _call(_service(request).aggregation, start_date, end_date, group_by, bucket_minutes)


@router.get("/forecast-versions", response_model=schemas.ForecastVersionsResponse)
def forecast_versions(request: Request, start_date: Optional[date] = _start(), end_date: Optional[date] = _end(),
                      include_mape: bool = False,
                      include_post_cutoff: bool = Query(False, description="Revision analysis only; never affects decision-time metrics."),
                      lead_bins: Optional[str] = Query(None, description="Comma-separated increasing lead-time edges in hours, e.g. 0,6,12,24,48,96")):
    """(a) Decision-time evaluation and (b) supplementary revision analysis, kept separate."""
    bins = None
    if lead_bins:
        try:
            bins = [float(x) for x in lead_bins.split(",")]
        except ValueError:
            raise HTTPException(status_code=422, detail="lead_bins must be comma-separated numbers")
    return _call(_service(request).forecast_versions, start_date, end_date, include_mape, include_post_cutoff, bins)


@router.get("/data-quality", response_model=schemas.DataQualityResponse)
def data_quality(request: Request, start_date: Optional[date] = _start(), end_date: Optional[date] = _end(),
                 sample_limit: int = Query(20, ge=0, le=1000, description="Number of excluded-interval examples to return.")):
    """Expected vs valid intervals, mutually exclusive exclusion reasons, and coverage."""
    return _call(_service(request).data_quality, start_date, end_date, sample_limit)
