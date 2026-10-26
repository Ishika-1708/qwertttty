"""Module 1 -> Module 2 data contract (the 'agreed output').

Module 2 consumes three tabular inputs. All timestamps MUST be timezone-aware
(they are converted to UTC on entry). Naive timestamps are rejected, never guessed.

expected_intervals  - one row per delivery interval that SHOULD be evaluated
    interval_start_utc            datetime64[tz]  start of delivery interval (unique)
    decision_cutoff_utc           datetime64[tz]  last instant at which a forecast was usable for
                                                  the purchasing decision for this interval
    selected_publish_time_utc     datetime64[tz]  OPTIONAL. Module 1's own selection; used only as a
                                                  cross-check (mismatch count), never as the source of truth.

forecasts           - EVERY published forecast version Module 1 can retain (not only the selected one)
    interval_start_utc            datetime64[tz]  delivery interval the forecast refers to
    publish_time_utc              datetime64[tz]  when the forecast became AVAILABLE (distinct from delivery time)
    forecast_mw                   numeric         forecast generation
    unit                          str             must equal config.expected_unit
    quality_flag                  str             OPTIONAL, default "OK". Anything other than "OK"
                                                  (e.g. "INVALID", "DUPLICATE") is excluded. Null flag => excluded.

actuals             - one row per delivery interval (duplicates tolerated per README rule)
    interval_start_utc            datetime64[tz]
    actual_mw                     numeric
    unit                          str
    quality_flag                  str             OPTIONAL, default "OK"
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


class SchemaError(ValueError):
    """Module 1 input violates the agreed contract (reject, do not repair)."""


@dataclass
class Module1Dataset:
    expected_intervals: pd.DataFrame
    forecasts: pd.DataFrame
    actuals: pd.DataFrame
    dataset_id: str = "unspecified"
    dataset_version: str = "unspecified"
    meta: Optional[dict] = None


EXPECTED_REQUIRED = ["interval_start_utc", "decision_cutoff_utc"]
FORECAST_REQUIRED = ["interval_start_utc", "publish_time_utc", "forecast_mw", "unit"]
ACTUAL_REQUIRED = ["interval_start_utc", "actual_mw", "unit"]
