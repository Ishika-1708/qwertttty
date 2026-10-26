"""Forecast-version comparison.

Two analyses are kept strictly separate:

(a) DECISION-TIME EVALUATION  (authoritative)
    The forecast actually available at the purchasing cutoff, i.e. exactly the
    pairs in `ValidationResult.pairs`. Same function, same pairs as /summary.

(b) FORECAST REVISION ANALYSIS (supplementary)
    How accuracy varies with how far ahead a version was published (lead time)
    and how the forecast was revised between the first and the decision-time
    version. Cohort = intervals whose decision-time pair is valid, so (b) is
    always a decomposition of the same intervals as (a). Versions published
    AFTER the cutoff are excluded unless `include_post_cutoff=True`, in which
    case they are reported under scope "post_cutoff" and can never feed (a).

Data-contract requirement: (b) needs EVERY published version retained by Module 1
(interval_start_utc + publish_time_utc per row). If Module 1 supplies only the
selected forecast, history cannot be reconstructed and (b) reports
status="history_unavailable" instead of inventing anything.
"""
from __future__ import annotations

from typing import Optional, Sequence

import numpy as np
import pandas as pd

from .config import AnalyticsConfig
from .data_quality import ValidationResult
from .metrics import compute_metrics, metrics_from_pairs

_EPS = 1e-9


def decision_time_evaluation(result: ValidationResult, *, include_mape: bool = False) -> dict:
    m = metrics_from_pairs(
        result.pairs, include_mape=include_mape, mape_min_actual_mw=result.config.mape_min_actual_mw
    )
    return {
        "basis": "forecast available at decision_cutoff_utc (latest eligible published version)",
        "metrics": m.to_dict(),
    }


def _bucket_labels(bins: Sequence[float]):
    edges = [-np.inf, *bins, np.inf]
    labels = ["<0h"] + [f"{bins[i]:g}-{bins[i + 1]:g}h" for i in range(len(bins) - 1)] + [f">={bins[-1]:g}h"]
    return edges, labels


def revision_analysis(
    result: ValidationResult,
    *,
    include_post_cutoff: bool = False,
    lead_bins_hours: Optional[Sequence[float]] = None,
) -> dict:
    cfg: AnalyticsConfig = result.config
    bins = list(lead_bins_hours) if lead_bins_hours is not None else list(cfg.default_lead_bins_hours)
    if len(bins) < 2 or sorted(bins) != bins or len(set(bins)) != len(bins):
        raise ValueError("lead_bins_hours must be >= 2 strictly increasing numbers")

    out = {
        "status": "ok", "message": None, "include_post_cutoff": include_post_cutoff,
        "lead_bins_hours": bins, "versions_considered": 0, "by_lead_bucket": [], "revisions": None,
    }
    v = result.versions
    # cohort: intervals with a valid decision-time pair; versions with a usable value
    usable = v[(v["decision_pair_valid"]) & (v["forecast_state"] == "ok") & (v["actual_state"] == "ok")].copy()
    pre = usable[usable["eligible_at_cutoff"]]
    if pre.empty:
        out["status"] = "no_eligible_data"
        out["message"] = (
            "No eligible forecast version (valid, published at or before the decision cutoff, "
            "with a valid actual) exists in the selected period; nothing was estimated."
        )
        return out

    max_versions = int(v.groupby("interval_start_utc").size().max()) if len(v) else 0
    if max_versions <= 1:
        out["status"] = "history_unavailable"
        out["message"] = (
            "Only one forecast version per interval was supplied by Module 1, so forecast history "
            "cannot be reconstructed. Module 1 must retain every published version "
            "(interval_start_utc + publish_time_utc per row). Decision-time evaluation is unaffected."
        )
        return out

    scope = usable if include_post_cutoff else pre
    out["versions_considered"] = int(len(scope))
    edges, labels = _bucket_labels(bins)
    scope = scope.assign(
        scope=np.where(scope["eligible_at_cutoff"], "pre_cutoff", "post_cutoff"),
        lead_bucket=pd.cut(scope["lead_time_hours"], bins=edges, labels=labels, right=False).astype(object),
    )
    order = {lab: i for i, lab in enumerate(labels)}
    rows = []
    for (sc, lb), g in scope.groupby(["scope", "lead_bucket"], sort=False):
        m = compute_metrics(g["forecast_mw"].to_numpy(), g["actual_mw"].to_numpy())
        rows.append({
            "scope": sc, "lead_bucket": lb, "version_count": m.sample_count,
            "interval_count": int(g["interval_start_utc"].nunique()),
            "mae_mw": m.mae_mw, "rmse_mw": m.rmse_mw, "mbe_mw": m.mbe_mw,
        })
    rows.sort(key=lambda r: (r["scope"] != "pre_cutoff", order[r["lead_bucket"]]))
    out["by_lead_bucket"] = rows

    # first pre-cutoff version vs decision-time (last pre-cutoff) version, per interval
    p = pre.sort_values(["interval_start_utc", "publish_time_utc"])
    g = p.groupby("interval_start_utc")
    first = g.first()
    last = g.last()
    n = g.size()
    multi = n[n >= 2].index
    if len(multi):
        f0 = first.loc[multi, "forecast_mw"].to_numpy()
        f1 = last.loc[multi, "forecast_mw"].to_numpy()
        act = last.loc[multi, "actual_mw"].to_numpy()
        e0, e1 = np.abs(f0 - act), np.abs(f1 - act)
        d = e0 - e1
        out["revisions"] = {
            "intervals_with_multiple_versions": int(len(multi)),
            "mean_abs_revision_mw": float(np.mean(np.abs(f1 - f0))),
            "mean_signed_revision_mw": float(np.mean(f1 - f0)),
            "mean_abs_error_first_mw": float(np.mean(e0)),
            "mean_abs_error_decision_mw": float(np.mean(e1)),
            "improved_count": int((d > _EPS).sum()),
            "worsened_count": int((d < -_EPS).sum()),
            "unchanged_count": int((np.abs(d) <= _EPS).sum()),
        }
    return out


def compare_versions(result: ValidationResult, *, include_mape: bool = False, include_post_cutoff: bool = False,
                     lead_bins_hours: Optional[Sequence[float]] = None) -> dict:
    return {
        "decision_time_evaluation": decision_time_evaluation(result, include_mape=include_mape),
        "revision_analysis": revision_analysis(
            result, include_post_cutoff=include_post_cutoff, lead_bins_hours=lead_bins_hours
        ),
    }
