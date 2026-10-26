"""Service layer: turns a Module1Dataset + filters into JSON-ready dicts.

Routes call ONLY this module; this module calls the pure calculation modules.
No metric is computed anywhere else (and never in the dashboard), so every
number the UI shows is traceable to the same `ValidationResult.pairs`.
"""
from __future__ import annotations

import math
from dataclasses import replace
from datetime import date
from typing import Optional, Sequence

import numpy as np
import pandas as pd

from . import aggregations, forecast_comparison
from .config import (
    CALCULATION_VERSION, CUTOFF_RULE, ERROR_DEFINITION, SELECTION_RULE, AnalyticsConfig,
)
from .contract import Module1Dataset
from .data_quality import ValidationResult, validate
from .metrics import add_error_columns, metrics_from_pairs

NOTE_DESCRIPTIVE = (
    "Descriptive statistics only. Differences between groups do not establish a cause; "
    "small sample_count / low_sample groups carry little evidence."
)


# ------------------------------------------------------------------ JSON helpers
def _num(x):
    if x is None:
        return None
    try:
        if pd.isna(x):
            return None
    except (TypeError, ValueError):
        pass
    return float(x)


def _utc(ts) -> Optional[str]:
    return None if ts is None or pd.isna(ts) else ts.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def _local(ts, tz: str) -> Optional[str]:
    return None if ts is None or pd.isna(ts) else ts.tz_convert(tz).isoformat()


def _clean_records(df: pd.DataFrame) -> list:
    out = []
    for rec in df.to_dict("records"):
        out.append({
            k: (None if (v is None or (isinstance(v, float) and math.isnan(v)) or v is pd.NA) else
                (bool(v) if isinstance(v, (np.bool_,)) else int(v) if isinstance(v, np.integer) else
                 float(v) if isinstance(v, np.floating) else v))
            for k, v in rec.items()
        })
    return out


def _local_date(series: pd.Series, tz: str) -> pd.Series:
    return series.dt.tz_convert(tz).dt.strftime("%Y-%m-%d")


class AnalyticsService:
    def __init__(self, dataset: Module1Dataset, config: Optional[AnalyticsConfig] = None):
        self.dataset = dataset
        self.config = config or AnalyticsConfig()
        self._cache: dict = {}

    # ---------------------------------------------------------------- filtering
    def _filtered_dataset(self, start: Optional[date], end: Optional[date]) -> Module1Dataset:
        if start and end and start > end:
            raise ValueError("start_date must be <= end_date")
        if start is None and end is None:
            return self.dataset
        tz = self.config.aggregation_timezone

        def keep(df: pd.DataFrame) -> pd.DataFrame:
            if df.empty:
                return df
            d = _local_date(df["interval_start_utc"].dt.tz_convert("UTC"), tz)
            m = pd.Series(True, index=df.index)
            if start:
                m &= d >= start.isoformat()
            if end:
                m &= d <= end.isoformat()
            return df[m]

        ds = self.dataset
        return replace(ds, expected_intervals=keep(ds.expected_intervals), forecasts=keep(ds.forecasts), actuals=keep(ds.actuals))

    def validated(self, start: Optional[date] = None, end: Optional[date] = None) -> ValidationResult:
        key = (start, end)
        if key not in self._cache:
            self._cache[key] = validate(self._filtered_dataset(start, end), self.config)
        return self._cache[key]

    # ---------------------------------------------------------------- shared blocks
    def _period(self, r: ValidationResult, start, end) -> dict:
        iv = r.intervals["interval_start_utc"]
        return {
            "start_date": start.isoformat() if start else None,
            "end_date": end.isoformat() if end else None,
            "timezone": self.config.aggregation_timezone,
            "first_interval_utc": _utc(iv.min()) if len(iv) else None,
            "last_interval_utc": _utc(iv.max()) if len(iv) else None,
        }

    def _coverage(self, r: ValidationResult) -> dict:
        s = r.summary
        return {k: s[k] for k in (
            "expected_intervals", "valid_matched_pairs", "missing_forecasts", "missing_actuals",
            "missing_both", "no_eligible_forecasts", "invalid_pairs", "coverage_pct")}

    def _trace(self, r: ValidationResult) -> dict:
        return {
            "dataset_id": r.dataset_id, "dataset_version": r.dataset_version,
            "calculation_version": CALCULATION_VERSION, "pairs_fingerprint": r.fingerprint,
            "error_definition": ERROR_DEFINITION, "forecast_selection_rule": SELECTION_RULE,
            "cutoff_rule": CUTOFF_RULE, "unit": self.config.expected_unit,
            "aggregation_timezone": self.config.aggregation_timezone,
            "input_row_counts": {
                "forecast_rows": r.summary["informational"]["forecast_rows_received"],
                "actual_rows": r.summary["informational"]["actual_rows_received"],
                "expected_intervals": r.summary["expected_intervals"],
            },
        }

    # ---------------------------------------------------------------- endpoints
    def summary(self, start=None, end=None, include_mape: bool = False) -> dict:
        r = self.validated(start, end)
        m = metrics_from_pairs(r.pairs, include_mape=include_mape, mape_min_actual_mw=self.config.mape_min_actual_mw)
        return {
            "period": self._period(r, start, end),
            "metrics": m.to_dict(),
            "coverage": self._coverage(r),
            "unit": self.config.expected_unit,
            "error_sign_convention": ERROR_DEFINITION,
            "traceability": self._trace(r),
        }

    def intervals(self, start=None, end=None, status: str = "valid", limit: int = 1000, offset: int = 0) -> dict:
        if status not in ("valid", "excluded", "all"):
            raise ValueError("status must be one of: valid, excluded, all")
        if limit < 1 or offset < 0:
            raise ValueError("limit must be >= 1 and offset >= 0")
        r = self.validated(start, end)
        a = add_error_columns(r.intervals, mask=r.intervals["is_valid"])
        if status == "valid":
            a = a[a["is_valid"]]
        elif status == "excluded":
            a = a[~a["is_valid"]]
        total = int(len(a))
        page = a.iloc[offset: offset + limit]
        tz = self.config.display_timezone
        items = []
        for row in page.itertuples(index=False):
            items.append({
                "interval_start_utc": _utc(row.interval_start_utc),
                "interval_start_local": _local(row.interval_start_utc, tz),
                "decision_cutoff_utc": _utc(row.decision_cutoff_utc),
                "forecast_publish_time_utc": _utc(row.forecast_publish_time_utc),
                "lead_time_hours": _num(row.lead_time_hours),
                "forecast_mw": _num(row.forecast_mw),
                "actual_mw": _num(row.actual_mw),
                "error_mw": _num(row.error_mw),
                "abs_error_mw": _num(row.abs_error_mw),
                "status": "valid" if row.is_valid else "excluded",
                "exclusion_reason": None if row.is_valid else row.reason,
                "exclusion_detail": None if row.is_valid or not row.reason_detail else row.reason_detail,
                "issues": row.issues or None,
            })
        return {
            "period": self._period(r, start, end), "status_filter": status,
            "total": total, "limit": limit, "offset": offset, "items": items,
            "display_timezone": tz, "unit": self.config.expected_unit,
            "error_sign_convention": ERROR_DEFINITION, "traceability": self._trace(r),
        }

    def aggregation(self, start=None, end=None, group_by: str = "date", bucket_minutes: int = 60) -> dict:
        if group_by not in ("date", "time_of_day"):
            raise ValueError("group_by must be 'date' or 'time_of_day'")
        r = self.validated(start, end)
        if group_by == "date":
            df = aggregations.daily_metrics(r.intervals, self.config)
            bm = None
        else:
            df = aggregations.time_of_day_metrics(r.intervals, self.config, bucket_minutes)
            bm = bucket_minutes
        return {
            "period": self._period(r, start, end), "group_by": group_by, "bucket_minutes": bm,
            "timezone": self.config.aggregation_timezone, "unit": self.config.expected_unit,
            "groups": _clean_records(df), "note": NOTE_DESCRIPTIVE,
            "error_sign_convention": ERROR_DEFINITION, "traceability": self._trace(r),
        }

    def forecast_versions(self, start=None, end=None, include_mape: bool = False,
                          include_post_cutoff: bool = False, lead_bins_hours: Optional[Sequence[float]] = None) -> dict:
        r = self.validated(start, end)
        res = forecast_comparison.compare_versions(
            r, include_mape=include_mape, include_post_cutoff=include_post_cutoff, lead_bins_hours=lead_bins_hours)
        dt = res["decision_time_evaluation"]
        dt["coverage"] = self._coverage(r)
        return {
            "period": self._period(r, start, end),
            "decision_time_evaluation": dt, "revision_analysis": res["revision_analysis"],
            "unit": self.config.expected_unit, "note": NOTE_DESCRIPTIVE,
            "error_sign_convention": ERROR_DEFINITION, "traceability": self._trace(r),
        }

    def data_quality(self, start=None, end=None, sample_limit: int = 20) -> dict:
        if sample_limit < 0:
            raise ValueError("sample_limit must be >= 0")
        r = self.validated(start, end)
        s = r.summary
        ex = r.intervals[~r.intervals["is_valid"]].head(sample_limit)
        examples = [{
            "interval_start_utc": _utc(x.interval_start_utc), "reason": x.reason,
            "reason_detail": x.reason_detail or None, "issues": x.issues or None,
        } for x in ex.itertuples(index=False)]
        return {
            "period": self._period(r, start, end), "coverage": self._coverage(r),
            "exclusions_by_reason": s["exclusions_by_reason"],
            "invalid_detail_counts": s["invalid_detail_counts"],
            "informational": s["informational"],
            "excluded_examples": examples,
            "accounting_note": ("Exclusion reasons are mutually exclusive (one primary reason per interval, by "
                                "precedence), so valid_matched_pairs + sum(exclusions_by_reason) = expected_intervals."),
            "traceability": self._trace(r),
        }
