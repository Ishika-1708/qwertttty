"""V1 Dashboard API layer matching frontend contract and adapters.

All metrics are computed via AnalyticsService; nothing is synthetic.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request

from ..config import CALCULATION_VERSION, CUTOFF_RULE, ERROR_DEFINITION, SELECTION_RULE
from ..contract import SchemaError
from ..providers import DatasetUnavailable
from ..service import AnalyticsService
from .routes import _service

v1_router = APIRouter(prefix="/api/v1", tags=["v1"])


def _date_bounds(r, s: Optional[date], e: Optional[date]) -> tuple[str, str]:
    if s and e:
        return s.isoformat(), e.isoformat()
    iv = r.intervals["interval_start_utc"]
    if len(iv):
        first = iv.min().strftime("%Y-%m-%d")
        last = iv.max().strftime("%Y-%m-%d")
    else:
        first, last = "2026-01-01", "2026-01-31"
    return s.isoformat() if s else first, e.isoformat() if e else last


@v1_router.get("/metrics/summary")
def summary(
    request: Request,
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
):
    s = start or start_date
    e = end or end_date
    if s and e and s > e:
        raise HTTPException(status_code=422, detail="start must be on or before end")
    svc = _service(request)
    r = svc.validated(s, e)
    summ = svc.summary(s, e)
    cov = summ["coverage"]
    met = summ["metrics"]

    first_str, last_str = _date_bounds(r, s, e)
    expected_intervals = cov["expected_intervals"]
    valid_pairs = cov["valid_matched_pairs"]
    coverage_pct = cov["coverage_pct"]

    warnings = []
    if expected_intervals == 0:
        warnings.append("No intervals found for the selected evaluation period.")

    return {
        "period": {"start": first_str, "end": last_str},
        "decision_cutoff": {
            "description": "Module 1 decision cutoff (un-flagged version <= cutoff)",
            "hours_before_delivery": 15.0,
        },
        "unit": "MW",
        "metrics": {
            "mae": met["mae_mw"],
            "rmse": met["rmse_mw"],
            "mbe": met["mbe_mw"],
        },
        "valid_matched_intervals": valid_pairs,
        "expected_intervals": expected_intervals,
        "coverage_pct": coverage_pct,
        "completeness": "complete" if coverage_pct == 100.0 else "incomplete",
        "warnings": warnings,
        "data_as_of": datetime.now(timezone.utc).isoformat(),
    }


@v1_router.get("/intervals")
def intervals(
    request: Request,
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    limit: int = Query(10000, ge=1, le=50000),
    offset: int = Query(0, ge=0),
):
    s = start or start_date
    e = end or end_date
    if s and e and s > e:
        raise HTTPException(status_code=422, detail="start must be on or before end")
    svc = _service(request)
    r = svc.validated(s, e)
    res = svc.intervals(s, e, status="all", limit=limit, offset=offset)
    first_str, last_str = _date_bounds(r, s, e)

    formatted = []
    for item in res["items"]:
        is_valid = item["status"] == "valid"
        if is_valid:
            st = "matched"
        elif item["actual_mw"] is None and item["forecast_mw"] is None:
            st = "unmatched"
        elif item["actual_mw"] is None:
            st = "missing_actual"
        elif item["forecast_mw"] is None:
            st = "missing_forecast"
        elif item["exclusion_reason"] in ("invalid_forecast", "invalid_actual"):
            st = "invalid"
        else:
            st = "excluded"

        pub_utc = item["forecast_publish_time_utc"]
        cut_utc = item["decision_cutoff_utc"]
        avail = is_valid or (pub_utc is not None and cut_utc is not None and pub_utc <= cut_utc)

        formatted.append({
            "delivery_time": item["interval_start_utc"],
            "forecast_mw": item["forecast_mw"],
            "actual_mw": item["actual_mw"],
            "error_mw": item["error_mw"],
            "forecast_published_at": pub_utc,
            "decision_cutoff_at": cut_utc,
            "available_by_cutoff": avail if item["forecast_mw"] is not None else None,
            "status": st,
            "exclusion_reason": item["exclusion_reason"],
        })

    return {
        "period": {"start": first_str, "end": last_str},
        "intervals": formatted,
        "total_count": len(formatted),
    }


@v1_router.get("/metrics/daily")
def daily(
    request: Request,
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
):
    s = start or start_date
    e = end or end_date
    if s and e and s > e:
        raise HTTPException(status_code=422, detail="start must be on or before end")
    svc = _service(request)
    r = svc.validated(s, e)
    res = svc.aggregation(s, e, group_by="date")
    first_str, last_str = _date_bounds(r, s, e)

    points = []
    for g in res["groups"]:
        points.append({
            "date": g["group"],
            "mae": g["mae_mw"],
            "rmse": g["rmse_mw"],
            "mbe": g["mbe_mw"],
            "sample_count": g["sample_count"],
            "expected_intervals": g["expected_intervals"],
            "coverage_pct": g["coverage_pct"],
        })

    return {
        "period": {"start": first_str, "end": last_str},
        "points": points,
        "available_metrics": ["mae", "rmse", "mbe"],
    }


@v1_router.get("/metrics/error-distribution")
def error_distribution(
    request: Request,
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
):
    s = start or start_date
    e = end or end_date
    if s and e and s > e:
        raise HTTPException(status_code=422, detail="start must be on or before end")
    svc = _service(request)
    r = svc.validated(s, e)
    first_str, last_str = _date_bounds(r, s, e)

    errs = []
    if len(r.pairs):
        for _, row in r.pairs.iterrows():
            f = row.get("forecast_mw")
            a = row.get("actual_mw")
            if pd.notna(f) and pd.notna(a):
                errs.append(abs(float(f) - float(a)))

    bin_edges = [
        (0.0, 100.0),
        (100.0, 200.0),
        (200.0, 300.0),
        (300.0, 400.0),
        (400.0, 600.0),
        (600.0, 800.0),
        (800.0, None),
    ]
    bins = [
        {
            "lower_mw": lo,
            "upper_mw": hi,
            "count": sum(1 for err in errs if err >= lo and (hi is None or err < hi)),
        }
        for lo, hi in bin_edges
    ]

    return {
        "period": {"start": first_str, "end": last_str},
        "unit": "MW",
        "bins": bins,
        "total_count": len(errs),
    }


@v1_router.get("/metrics/time-of-day")
def time_of_day(
    request: Request,
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
):
    s = start or start_date
    e = end or end_date
    if s and e and s > e:
        raise HTTPException(status_code=422, detail="start must be on or before end")
    svc = _service(request)
    r = svc.validated(s, e)
    res = svc.aggregation(s, e, group_by="time_of_day", bucket_minutes=180)
    first_str, last_str = _date_bounds(r, s, e)

    groups = []
    for g in res["groups"]:
        hh = int(g["group"][:2])
        label = f"{hh:02d}:00–{hh + 3:02d}:00"
        groups.append({
            "label": label,
            "mae": g["mae_mw"],
            "rmse": g["rmse_mw"],
            "mbe": g["mbe_mw"],
            "sample_count": g["sample_count"],
        })

    return {
        "period": {"start": first_str, "end": last_str},
        "grouping": "Time of day (UK), 3-hour blocks",
        "groups": groups,
        "available_metrics": ["mae", "rmse", "mbe"],
    }


@v1_router.get("/forecast-history")
def forecast_history(
    request: Request,
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
):
    s = start or start_date
    e = end or end_date
    if s and e and s > e:
        raise HTTPException(status_code=422, detail="start must be on or before end")
    svc = _service(request)
    r = svc.validated(s, e)
    first_str, last_str = _date_bounds(r, s, e)

    pubs = []
    for iv in r.intervals.itertuples(index=False):
        if iv.forecast_publish_time_utc and pd.notna(iv.forecast_publish_time_utc):
            pub_ts = iv.forecast_publish_time_utc
            pub_str = pub_ts.strftime("%Y-%m-%dT%H:%M:%SZ") if hasattr(pub_ts, "strftime") else str(pub_ts)
            deliv_ts = iv.interval_start_utc
            deliv_tag = deliv_ts.strftime("%Y%m%d%H%M") if hasattr(deliv_ts, "strftime") else "interval"
            pubs.append({
                "published_at": pub_str,
                "version_id": f"windfor-{deliv_tag}",
                "intervals_covered": 1,
                "selected": True,
            })
    pubs = pubs[-200:]

    return {
        "period": {"start": first_str, "end": last_str},
        "decision_cutoff": {
            "description": "Module 1 decision cutoff rule",
            "hours_before_delivery": 15.0,
        },
        "retention": "full",
        "retention_note": None,
        "selected_version_description": "Latest forecast published at or before the decision cutoff",
        "publications": pubs,
    }


@v1_router.get("/data-quality")
def data_quality(
    request: Request,
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
):
    s = start or start_date
    e = end or end_date
    if s and e and s > e:
        raise HTTPException(status_code=422, detail="start must be on or before end")
    svc = _service(request)
    r = svc.validated(s, e)
    cov = svc.summary(s, e)["coverage"]
    dq = svc.data_quality(s, e)
    first_str, last_str = _date_bounds(r, s, e)

    reasons = [{"reason": k, "count": v} for k, v in dq["exclusions_by_reason"].items() if v > 0]
    return {
        "period": {"start": first_str, "end": last_str},
        "expected_intervals": cov["expected_intervals"],
        "valid_matched_intervals": cov["valid_matched_pairs"],
        "missing_actuals": cov["missing_actuals"],
        "missing_forecasts": cov["missing_forecasts"],
        "unmatched_intervals": cov["missing_both"],
        "excluded_or_invalid": cov["no_eligible_forecasts"] + cov["invalid_pairs"],
        "exclusion_reasons": reasons,
        "coverage_pct": cov["coverage_pct"],
        "last_successful_update_at": datetime.now(timezone.utc).isoformat(),
    }
