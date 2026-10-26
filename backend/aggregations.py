"""Descriptive aggregations: by delivery date and by time of day.

Timezone convention (single, explicit): dates and time-of-day buckets are derived
from `interval_start_utc` converted ONCE to `config.aggregation_timezone`
(default UTC). Local-time display (`display_timezone`) is a presentation concern
handled in service.py and never affects grouping.

These are DESCRIPTIVE patterns. A bucket with a larger error does not show that any
particular factor (weather, time of day, curtailment ...) caused it; no causal claim
is made or supported by this module.

Every group carries `expected_intervals`, `sample_count` and `coverage_pct`, so a
low error computed from very few pairs is visibly low-evidence (`low_sample`).
Groups with zero valid pairs are retained with `None` metrics - never 0.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from .config import AnalyticsConfig
from .metrics import compute_metrics

AGG_COLUMNS = [
    "group", "expected_intervals", "sample_count", "coverage_pct",
    "mae_mw", "rmse_mw", "mbe_mw", "low_sample",
]


def _grouped(audit: pd.DataFrame, keys: pd.Series, cfg: AnalyticsConfig) -> pd.DataFrame:
    rows = []
    frame = audit.assign(_k=keys.to_numpy())
    for key, g in frame.groupby("_k", sort=True):
        valid = g[g["is_valid"]]
        m = compute_metrics(valid["forecast_mw"].to_numpy(), valid["actual_mw"].to_numpy())
        n_exp = int(len(g))
        rows.append({
            "group": key,
            "expected_intervals": n_exp,
            "sample_count": m.sample_count,
            "coverage_pct": m.sample_count / n_exp * 100.0 if n_exp else None,
            "mae_mw": m.mae_mw, "rmse_mw": m.rmse_mw, "mbe_mw": m.mbe_mw,
            "low_sample": m.sample_count < cfg.low_sample_threshold,
        })
    return pd.DataFrame(rows, columns=AGG_COLUMNS)


def daily_metrics(audit: pd.DataFrame, config: Optional[AnalyticsConfig] = None) -> pd.DataFrame:
    """MAE/RMSE/MBE by delivery date (YYYY-MM-DD in aggregation_timezone)."""
    cfg = config or AnalyticsConfig()
    if audit.empty:
        return pd.DataFrame(columns=AGG_COLUMNS)
    local = audit["interval_start_utc"].dt.tz_convert(cfg.aggregation_timezone)
    return _grouped(audit, local.dt.strftime("%Y-%m-%d"), cfg)


def time_of_day_metrics(audit: pd.DataFrame, config: Optional[AnalyticsConfig] = None, bucket_minutes: int = 60) -> pd.DataFrame:
    """MAE/RMSE/MBE by wall-clock time-of-day bucket ("HH:MM" = bucket start) in aggregation_timezone."""
    cfg = config or AnalyticsConfig()
    if bucket_minutes <= 0 or 1440 % bucket_minutes != 0 or bucket_minutes % cfg.interval_minutes != 0:
        raise ValueError(
            f"bucket_minutes must divide 1440 and be a multiple of interval_minutes ({cfg.interval_minutes})"
        )
    if audit.empty:
        return pd.DataFrame(columns=AGG_COLUMNS)
    local = audit["interval_start_utc"].dt.tz_convert(cfg.aggregation_timezone)
    minutes = local.dt.hour * 60 + local.dt.minute
    start = (minutes // bucket_minutes) * bucket_minutes
    label = start.map(lambda m: f"{m // 60:02d}:{m % 60:02d}")
    return _grouped(audit, label, cfg)
