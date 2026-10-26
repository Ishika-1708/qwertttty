"""How Module 2 obtains Module 1's standardized dataset.

The transport between modules is an OPEN QUESTION (README, Q1). Two providers are
supplied behind one protocol so the API never depends on the choice.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, Protocol

import pandas as pd

from .contract import Module1Dataset


class DatasetProvider(Protocol):
    def get_dataset(self) -> Module1Dataset: ...


class DatasetUnavailable(RuntimeError):
    pass


class InMemoryProvider:
    def __init__(self, dataset: Module1Dataset):
        self._ds = dataset

    def get_dataset(self) -> Module1Dataset:
        return self._ds


class FileDatasetProvider:
    """Reads expected_intervals.csv, forecasts.csv, actuals.csv (+ optional meta.json)
    or matched_dataset.csv from a directory. Timestamp columns must be ISO-8601 WITH offset/Z (parsed as UTC)."""

    def __init__(self, directory: Optional[str] = None):
        if directory:
            self.directory = Path(directory)
        elif os.environ.get("MODULE1_DATA_DIR"):
            self.directory = Path(os.environ["MODULE1_DATA_DIR"])
        else:
            candidates = [
                Path("output"),
                Path("../output"),
                Path(__file__).resolve().parent.parent / "output",
                Path("."),
            ]
            self.directory = next(
                (c for c in candidates if (c / "expected_intervals.csv").is_file() or (c / "matched_dataset.csv").is_file()),
                Path("output")
            )

    def get_dataset(self) -> Module1Dataset:
        d = self.directory
        files = {n: d / f"{n}.csv" for n in ("expected_intervals", "forecasts", "actuals")}
        missing = [str(p) for p in files.values() if not p.is_file()]
        if missing and (d / "matched_dataset.csv").is_file():
            matched = pd.read_csv(d / "matched_dataset.csv")
            exp = pd.DataFrame({
                "interval_start_utc": pd.to_datetime(matched["delivery_time"], utc=True),
                "decision_cutoff_utc": pd.to_datetime(matched["decision_cutoff"], utc=True),
                "selected_publish_time_utc": pd.to_datetime(matched["forecast_publish_time"], utc=True),
            })
            fc = matched.dropna(subset=["forecast_publish_time", "forecast_generation_mw"])
            forecasts = pd.DataFrame({
                "interval_start_utc": pd.to_datetime(fc["delivery_time"], utc=True),
                "publish_time_utc": pd.to_datetime(fc["forecast_publish_time"], utc=True),
                "forecast_mw": fc["forecast_generation_mw"].astype(float),
                "unit": "MW",
                "quality_flag": "OK",
            })
            act = matched.dropna(subset=["actual_generation_mw"])
            actuals = pd.DataFrame({
                "interval_start_utc": pd.to_datetime(act["delivery_time"], utc=True),
                "actual_mw": act["actual_generation_mw"].astype(float),
                "unit": "MW",
                "quality_flag": "OK",
            })
            meta_p = d / "meta.json"
            meta = json.loads(meta_p.read_text()) if meta_p.is_file() else {}
            newest = (d / "matched_dataset.csv").stat().st_mtime_ns
            return Module1Dataset(
                expected_intervals=exp,
                forecasts=forecasts,
                actuals=actuals,
                dataset_id=meta.get("dataset_id", "elexon-wind-jan2026"),
                dataset_version=str(meta.get("dataset_version", newest)),
                meta=meta,
            )
        if not str(d) or missing:
            raise DatasetUnavailable(f"Module 1 dataset not found (missing: {missing or str(d)})")
        meta_p = d / "meta.json"
        meta = json.loads(meta_p.read_text()) if meta_p.is_file() else {}

        def read(name, ts_cols):
            df = pd.read_csv(files[name])
            for c in ts_cols:
                if c in df.columns:
                    df[c] = pd.to_datetime(df[c], utc=True)
            return df

        newest = max(p.stat().st_mtime_ns for p in files.values())
        return Module1Dataset(
            expected_intervals=read("expected_intervals", ["interval_start_utc", "decision_cutoff_utc", "selected_publish_time_utc"]),
            forecasts=read("forecasts", ["interval_start_utc", "publish_time_utc"]),
            actuals=read("actuals", ["interval_start_utc"]),
            dataset_id=meta.get("dataset_id", d.name),
            dataset_version=str(meta.get("dataset_version", newest)),
            meta=meta,
        )
