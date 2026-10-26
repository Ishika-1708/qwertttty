"""Synthetic Module 1 datasets with known answers. Not real Elexon data."""
from __future__ import annotations

import numpy as np
import pandas as pd

from module2.contract import Module1Dataset

T0 = pd.Timestamp("2026-01-05T00:00:00Z")
CUTOFF_LEAD_H = 12


def starts(n: int, t0: pd.Timestamp = T0):
    return [t0 + pd.Timedelta(minutes=30 * i) for i in range(n)]


def _ts(values):
    return pd.Series(pd.to_datetime(values, utc=True)).dt.as_unit("ns")


def empty_forecasts() -> pd.DataFrame:
    return pd.DataFrame({
        "interval_start_utc": pd.Series(pd.array([], dtype="datetime64[ns, UTC]")),
        "publish_time_utc": pd.Series(pd.array([], dtype="datetime64[ns, UTC]")),
        "forecast_mw": pd.Series([], dtype="float64"),
        "unit": pd.Series([], dtype="object"),
        "quality_flag": pd.Series([], dtype="object"),
    })


def empty_actuals() -> pd.DataFrame:
    return pd.DataFrame({
        "interval_start_utc": pd.Series(pd.array([], dtype="datetime64[ns, UTC]")),
        "actual_mw": pd.Series([], dtype="float64"),
        "unit": pd.Series([], dtype="object"),
        "quality_flag": pd.Series([], dtype="object"),
    })


def expected_frame(n: int, lead_h: float = CUTOFF_LEAD_H, t0: pd.Timestamp = T0) -> pd.DataFrame:
    s = starts(n, t0)
    return pd.DataFrame({
        "interval_start_utc": _ts(s),
        "decision_cutoff_utc": _ts([x - pd.Timedelta(hours=lead_h) for x in s]),
    })


def simple_dataset(forecasts, actuals, lead_h: float = CUTOFF_LEAD_H, publish_before_cutoff_h: float = 1.0,
                   t0: pd.Timestamp = T0) -> Module1Dataset:
    """One forecast version per interval (published 1h before the cutoff) - hand-checkable cases.
    `None` entries in forecasts/actuals mean 'row present with a null value'."""
    assert len(forecasts) == len(actuals)
    n = len(forecasts)
    s = starts(n, t0)
    exp = expected_frame(n, lead_h, t0)
    fc = pd.DataFrame({
        "interval_start_utc": _ts(s),
        "publish_time_utc": _ts([x - pd.Timedelta(hours=lead_h + publish_before_cutoff_h) for x in s]),
        "forecast_mw": pd.Series(forecasts, dtype="object"),
        "unit": "MW", "quality_flag": "OK",
    })
    ac = pd.DataFrame({
        "interval_start_utc": _ts(s), "actual_mw": pd.Series(actuals, dtype="object"),
        "unit": "MW", "quality_flag": "OK",
    })
    return Module1Dataset(exp, fc, ac, dataset_id="simple", dataset_version="v1")


def make_dataset(n: int = 96, lead_h: float = CUTOFF_LEAD_H) -> Module1Dataset:
    """Four versions per interval k with actual A_k = 5000 + 10k:
         publish = start-48h  F = A + 300   (eligible, early)
         publish = start-24h  F = A + 100   (eligible)
         publish = start-12h  F = A + 50 (k even) / A - 20 (k odd)  (== cutoff -> eligible; DECISION version)
         publish = start- 6h  F = A         (AFTER cutoff -> must never be used)
    Decision-time errors alternate +50/-20, so for even n:
         MAE = 35, MBE = 15, RMSE = sqrt((2500+400)/2).
    """
    s = starts(n)
    A = np.array([5000 + 10 * k for k in range(n)], dtype=float)
    dec = np.where(np.arange(n) % 2 == 0, A + 50, A - 20)
    rows = []
    for off, vals in ((48, A + 300), (24, A + 100), (12, dec), (6, A)):
        rows.append(pd.DataFrame({
            "interval_start_utc": _ts(s),
            "publish_time_utc": _ts([x - pd.Timedelta(hours=off) for x in s]),
            "forecast_mw": vals, "unit": "MW", "quality_flag": "OK",
        }))
    fc = pd.concat(rows, ignore_index=True)
    ac = pd.DataFrame({"interval_start_utc": _ts(s), "actual_mw": A, "unit": "MW", "quality_flag": "OK"})
    return Module1Dataset(expected_frame(n, lead_h), fc, ac, dataset_id="synthetic", dataset_version="v1")
