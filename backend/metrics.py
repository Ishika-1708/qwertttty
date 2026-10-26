"""Interval-level errors and aggregate accuracy metrics.

PURE functions of already-validated numeric input. No I/O, no pandas state, no
knowledge of routes. Convention (single source of truth for the whole platform):

    e   = F - A        signed error  (> 0 overforecast, < 0 underforecast)
    |e|                absolute error
    MAE  = mean(|e|)
    RMSE = sqrt(mean(e^2))
    MBE  = mean(e)

Missing values are NEVER coerced to zero. This module refuses non-finite input
(a programming error: data_quality.py must have excluded it) and returns
`None` metrics - not 0.0 - when there are no samples.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional, Sequence, Tuple

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class MetricSummary:
    sample_count: int
    mae_mw: Optional[float]
    rmse_mw: Optional[float]
    mbe_mw: Optional[float]
    mape_pct: Optional[float] = None            # only populated when include_mape=True
    mape_sample_count: Optional[int] = None
    mape_excluded_count: Optional[int] = None   # pairs dropped from MAPE because actual < floor

    def to_dict(self) -> dict:
        return asdict(self)


def _as_validated_arrays(forecast, actual) -> Tuple[np.ndarray, np.ndarray]:
    f = np.asarray(forecast, dtype="float64")
    a = np.asarray(actual, dtype="float64")
    if f.ndim != 1 or a.ndim != 1 or f.shape != a.shape:
        raise ValueError("forecast and actual must be 1-D arrays of equal length")
    if not (np.isfinite(f).all() and np.isfinite(a).all()):
        raise ValueError(
            "metrics received non-finite values; input must be validated by data_quality first "
            "(missing values must be excluded, never treated as zero)"
        )
    return f, a


def signed_errors(forecast, actual) -> Tuple[np.ndarray, np.ndarray]:
    """Return (e, |e|) with e = forecast - actual."""
    f, a = _as_validated_arrays(forecast, actual)
    e = f - a
    return e, np.abs(e)


def compute_metrics(
    forecast: Sequence[float],
    actual: Sequence[float],
    *,
    include_mape: bool = False,
    mape_min_actual_mw: float = 100.0,
) -> MetricSummary:
    """Aggregate MAE / RMSE / MBE (and optionally MAPE) over matched pairs.

    MAPE = mean(|e| / A) * 100 computed ONLY over pairs with A >= mape_min_actual_mw
    (and A > 0). Excluded pairs are counted in `mape_excluded_count`; if none qualify,
    MAPE is None. MAPE is optional, secondary, and unstable for small actuals.
    """
    e, abs_e = signed_errors(forecast, actual)
    n = int(e.size)
    mape = mape_n = mape_excl = None
    if include_mape:
        mape_n = 0
        mape_excl = n
    if n == 0:
        return MetricSummary(0, None, None, None, None, mape_n, mape_excl)

    mae = float(np.mean(abs_e))
    rmse = float(np.sqrt(np.mean(e * e)))
    mbe = float(np.mean(e))

    if include_mape:
        a = np.asarray(actual, dtype="float64")
        ok = (a > 0) & (a >= mape_min_actual_mw)
        mape_n = int(ok.sum())
        mape_excl = n - mape_n
        if mape_n > 0:
            mape = float(np.mean(abs_e[ok] / a[ok]) * 100.0)
    return MetricSummary(n, mae, rmse, mbe, mape, mape_n, mape_excl)


def add_error_columns(
    df: pd.DataFrame,
    *,
    forecast_col: str = "forecast_mw",
    actual_col: str = "actual_mw",
    mask: Optional[pd.Series] = None,
) -> pd.DataFrame:
    """Return a copy of `df` with `error_mw` and `abs_error_mw`.

    Rows where `mask` is False (e.g. excluded intervals) get NaN, never 0.
    """
    out = df.copy()
    out["error_mw"] = np.nan
    out["abs_error_mw"] = np.nan
    sel = np.ones(len(out), dtype=bool) if mask is None else mask.to_numpy(dtype=bool)
    if sel.any():
        e, abs_e = signed_errors(out.loc[sel, forecast_col], out.loc[sel, actual_col])
        out.loc[sel, "error_mw"] = e
        out.loc[sel, "abs_error_mw"] = abs_e
    return out


def metrics_from_pairs(pairs: pd.DataFrame, **kwargs) -> MetricSummary:
    """Convenience wrapper for a validated `pairs` frame (forecast_mw, actual_mw)."""
    return compute_metrics(pairs["forecast_mw"].to_numpy(), pairs["actual_mw"].to_numpy(), **kwargs)
