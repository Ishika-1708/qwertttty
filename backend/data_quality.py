"""Validation, forecast selection, matching and exclusion accounting.

Input : a `Module1Dataset` (see contract.py).
Output: a `ValidationResult` holding
    intervals - audit table, EXACTLY ONE ROW PER EXPECTED INTERVAL, with a single
                primary `reason` (so exclusions are mutually exclusive and sum to
                expected - valid) plus an `issues` string listing every problem found
    pairs     - the valid matched pairs. EVERY metric on the platform is computed from
                this frame (or from `intervals` filtered on `is_valid`), which is what
                keeps the dashboard internally consistent.
    versions  - every un-flagged forecast version with cutoff eligibility, for
                forecast_comparison.py
    summary   - counts and coverage

Validation rules (documented, deterministic)
--------------------------------------------
V1  Timestamps must be tz-aware (else SchemaError); converted to UTC.
V2  Numeric value states:  null/NaN -> "missing";  non-numeric text -> "non_numeric";
    +/-inf -> "non_finite";  < 0 -> "negative" (unless allow_negative_values);
    otherwise "ok". Missing is never replaced by 0.
V3  Unit must equal config.expected_unit (case-insensitive) else "unit_mismatch". No conversion.
V4  quality_flag != "OK" (or null) -> row is "flagged" and treated as non-existent.
V5  Duplicates (same interval for actuals; same interval + publish_time for forecasts),
    after removing flagged rows:  if all remaining rows agree on (state, value) they
    collapse to one; if they disagree the key is "ambiguous_duplicate" and the interval
    is EXCLUDED (we refuse to choose). Expected intervals themselves must be unique (SchemaError).
V6  Forecast eligibility: publish_time_utc <= decision_cutoff_utc (inclusive). Later
    versions never influence a decision-time metric.
V7  Selection: latest eligible un-flagged version. If it is unusable the interval is
    excluded (no silent fallback to an older version).
V8  Records for intervals outside expected_intervals are ignored and counted.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from .config import AnalyticsConfig
from .contract import (
    ACTUAL_REQUIRED,
    EXPECTED_REQUIRED,
    FORECAST_REQUIRED,
    Module1Dataset,
    SchemaError,
)

# Primary (mutually exclusive) exclusion reasons, in precedence order.
REASON_VALID = "valid"
EXCLUSION_REASONS = (
    "missing_forecast_and_actual",
    "missing_actual",
    "missing_forecast",
    "no_eligible_forecast",
    "invalid_forecast",
    "invalid_actual",
)


# --------------------------------------------------------------------------- helpers
def build_expected_intervals(start_utc, end_utc, *, interval_minutes: int = 30, cutoff_lead_hours: float = 12.0) -> pd.DataFrame:
    """Helper for tests/fallback ONLY: [start, end) at a fixed step with cutoff = start - lead.
    In production the cutoffs come from Module 1 (contract.py)."""
    starts = pd.date_range(start_utc, end_utc, freq=f"{interval_minutes}min", inclusive="left", tz="UTC")
    return pd.DataFrame({
        "interval_start_utc": starts,
        "decision_cutoff_utc": starts - pd.Timedelta(hours=cutoff_lead_hours),
    })


def classify_numeric(values: pd.Series, allow_negative: bool = False):
    """Return (float values with NaN where unusable, state Series). See rule V2."""
    is_null = values.isna()
    num = pd.to_numeric(values, errors="coerce").astype("float64")
    non_numeric = (~is_null) & num.isna()
    non_finite = num.notna() & ~np.isfinite(num)
    negative = num.notna() & np.isfinite(num) & (num < 0) & (not allow_negative)
    state = np.full(len(values), "ok", dtype=object)
    state[negative.to_numpy()] = "negative"
    state[non_finite.to_numpy()] = "non_finite"
    state[non_numeric.to_numpy()] = "non_numeric"
    state[is_null.to_numpy()] = "missing"
    state_s = pd.Series(state, index=values.index)
    return num.where(state_s == "ok"), state_s


def _as_utc(series: pd.Series, label: str, allow_null: bool = False) -> pd.Series:
    if len(series) == 0:
        return pd.Series(pd.array([], dtype="datetime64[ns, UTC]"), index=series.index)
    if not isinstance(series.dtype, pd.DatetimeTZDtype):
        raise SchemaError(f"{label} must be timezone-aware datetimes (naive/str timestamps are rejected)")
    if not allow_null and series.isna().any():
        raise SchemaError(f"{label} contains null timestamps")
    return series.dt.tz_convert("UTC").dt.as_unit("ns")


def _require(df: pd.DataFrame, cols, name: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise SchemaError(f"{name}: missing required columns {missing}")


def _row_states(df: pd.DataFrame, value_col: str, cfg: AnalyticsConfig) -> pd.DataFrame:
    """Row-level state/value per rules V2-V4. Precedence: flagged > (value state) > unit_mismatch."""
    value, vstate = classify_numeric(df[value_col], cfg.allow_negative_values)
    unit = df["unit"].astype("string").str.strip().str.upper()
    unit_ok = (unit == cfg.expected_unit.upper()).fillna(False).to_numpy(dtype=bool)
    if "quality_flag" in df.columns:
        flag = df["quality_flag"].astype("string").str.strip().str.upper()
        flagged = (flag != "OK").fillna(True).to_numpy(dtype=bool)
    else:
        flagged = np.zeros(len(df), dtype=bool)
    state = vstate.to_numpy(dtype=object).copy()
    state[(state == "ok") & ~unit_ok] = "unit_mismatch"
    state[flagged] = "flagged"
    return pd.DataFrame({"state": state, "value": value.to_numpy()}, index=df.index)


def _resolve_duplicates(rows: pd.DataFrame, keys: list) -> pd.DataFrame:
    """Collapse rows to one per key (rule V5). `rows` has `keys` + state + value."""
    r = rows.copy()
    r["is_flagged"] = r["state"].eq("flagged")
    r["unflagged"] = (~r["is_flagged"]).astype(int)
    sig = r["state"].astype(str) + "|" + r["value"].astype(str)
    r["sig"] = sig.where(~r["is_flagged"])
    g_all = r.groupby(keys, sort=False).agg(n_rows_total=("state", "size"), n_unflagged=("unflagged", "sum"))
    unf = r[~r["is_flagged"]]
    g_unf = unf.groupby(keys, sort=False).agg(
        n_distinct=("sig", "nunique"), state=("state", "first"), value=("value", "first")
    )
    res = g_all.join(g_unf, how="left").reset_index()
    res["state"] = res["state"].astype(object).where(res["n_unflagged"] > 0, "flagged")
    res["value"] = res["value"].astype("float64")
    amb = res["n_distinct"].fillna(0) > 1
    res.loc[amb, "state"] = "ambiguous_duplicate"
    res.loc[amb, "value"] = np.nan
    res["n_collapsed"] = np.where((res["n_unflagged"] > 1) & ~amb, res["n_unflagged"] - 1, 0)
    res["n_flagged_rows"] = res["n_rows_total"] - res["n_unflagged"]
    return res.drop(columns=["n_distinct"])


def _lookup(indexed: pd.Series, keys: pd.Series):
    return indexed.reindex(pd.Index(keys)).array


def _count_lookup(counts: pd.Series, keys: pd.Series) -> np.ndarray:
    return pd.Series(_lookup(counts, keys)).fillna(0).astype(int).to_numpy()


# ------------------------------------------------------------------------ result type
@dataclass
class ValidationResult:
    config: AnalyticsConfig
    intervals: pd.DataFrame
    pairs: pd.DataFrame
    versions: pd.DataFrame
    summary: dict
    dataset_id: str = "unspecified"
    dataset_version: str = "unspecified"

    @property
    def fingerprint(self) -> str:
        """Short hash of the valid matched pairs. Identical in every endpoint that used the same pairs."""
        p = self.pairs[["interval_start_utc", "forecast_mw", "actual_mw"]]
        payload = p.assign(interval_start_utc=p["interval_start_utc"].astype("int64")).to_csv(index=False)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


# -------------------------------------------------------------------------- main entry
def validate(dataset: Module1Dataset, config: Optional[AnalyticsConfig] = None) -> ValidationResult:
    cfg = config or AnalyticsConfig()

    # ---- schema + normalisation (V1) -------------------------------------------------
    exp = dataset.expected_intervals.copy()
    _require(exp, EXPECTED_REQUIRED, "expected_intervals")
    exp["interval_start_utc"] = _as_utc(exp["interval_start_utc"], "expected_intervals.interval_start_utc")
    exp["decision_cutoff_utc"] = _as_utc(exp["decision_cutoff_utc"], "expected_intervals.decision_cutoff_utc")
    has_m1_sel = "selected_publish_time_utc" in exp.columns
    if has_m1_sel:
        exp["selected_publish_time_utc"] = _as_utc(
            exp["selected_publish_time_utc"], "expected_intervals.selected_publish_time_utc", allow_null=True
        )
    if exp["interval_start_utc"].duplicated().any():
        raise SchemaError("expected_intervals contains duplicate interval_start_utc (ambiguous cutoffs) - rejected")
    exp = exp.sort_values("interval_start_utc").reset_index(drop=True)

    fc = dataset.forecasts.copy()
    _require(fc, FORECAST_REQUIRED, "forecasts")
    fc["interval_start_utc"] = _as_utc(fc["interval_start_utc"], "forecasts.interval_start_utc")
    fc["publish_time_utc"] = _as_utc(fc["publish_time_utc"], "forecasts.publish_time_utc", allow_null=True)

    ac = dataset.actuals.copy()
    _require(ac, ACTUAL_REQUIRED, "actuals")
    ac["interval_start_utc"] = _as_utc(ac["interval_start_utc"], "actuals.interval_start_utc")

    info = {
        "forecast_rows_received": int(len(fc)),
        "actual_rows_received": int(len(ac)),
    }

    # ---- V8: unexpected intervals; forecasts without a publish time ------------------
    in_f = fc["interval_start_utc"].isin(exp["interval_start_utc"])
    in_a = ac["interval_start_utc"].isin(exp["interval_start_utc"])
    info["unexpected_forecast_rows"] = int((~in_f).sum())
    info["unexpected_actual_rows"] = int((~in_a).sum())
    fc = fc[in_f].reset_index(drop=True)
    ac = ac[in_a].reset_index(drop=True)
    no_pub = fc["publish_time_utc"].isna()
    info["forecast_rows_missing_publish_time"] = int(no_pub.sum())  # cannot prove eligibility -> ignored
    fc = fc[~no_pub].reset_index(drop=True)

    # ---- row states + duplicate resolution (V2-V5) -----------------------------------
    fstates = _row_states(fc, "forecast_mw", cfg)
    astates = _row_states(ac, "actual_mw", cfg)
    info["forecast_rows_flagged_by_module1"] = int((fstates["state"] == "flagged").sum())
    info["actual_rows_flagged_by_module1"] = int((astates["state"] == "flagged").sum())

    fres = _resolve_duplicates(
        pd.concat([fc[["interval_start_utc", "publish_time_utc"]], fstates], axis=1),
        ["interval_start_utc", "publish_time_utc"],
    )
    ares = _resolve_duplicates(
        pd.concat([ac[["interval_start_utc"]], astates], axis=1), ["interval_start_utc"]
    )
    info["duplicate_forecast_rows_collapsed"] = int(fres["n_collapsed"].sum())
    info["duplicate_actual_rows_collapsed"] = int(ares["n_collapsed"].sum())

    # ---- forecast eligibility (V6) + selection (V7) ----------------------------------
    fv = fres.merge(exp[["interval_start_utc", "decision_cutoff_utc"]], on="interval_start_utc", how="left")
    fv["eligible_at_cutoff"] = fv["publish_time_utc"] <= fv["decision_cutoff_utc"]
    fv["lead_time_hours"] = (fv["interval_start_utc"] - fv["publish_time_utc"]).dt.total_seconds() / 3600.0
    nf = fv[fv["state"] != "flagged"].copy()
    n_any = fv.groupby("interval_start_utc").size()
    n_nf = nf.groupby("interval_start_utc").size()
    n_late = nf[~nf["eligible_at_cutoff"]].groupby("interval_start_utc").size()
    sel = (
        nf[nf["eligible_at_cutoff"]]
        .sort_values(["interval_start_utc", "publish_time_utc"])
        .groupby("interval_start_utc", sort=False)
        .tail(1)
        .set_index("interval_start_utc")
    )

    a = exp.copy()
    keys = a["interval_start_utc"]
    a["forecast_version_count"] = _count_lookup(n_nf, keys)
    a["late_version_count"] = _count_lookup(n_late, keys)
    n_any_v = _count_lookup(n_any, keys)
    n_nf_v = a["forecast_version_count"].to_numpy()
    a["forecast_publish_time_utc"] = _lookup(sel["publish_time_utc"], keys)
    sel_state = pd.Series(_lookup(sel["state"].astype(object), keys)).astype(object).to_numpy()
    sel_value = pd.Series(_lookup(sel["value"], keys)).to_numpy(dtype="float64")
    sel_collapsed = _count_lookup(sel["n_collapsed"], keys)
    has_sel = a["forecast_publish_time_utc"].notna().to_numpy()

    f_state = np.full(len(a), "ok", dtype=object)
    f_detail = np.full(len(a), "", dtype=object)
    for i in range(len(a)):  # small scalar branch table; clarity over vectorisation
        if n_any_v[i] == 0:
            f_state[i], f_detail[i] = "missing", "no_forecast_record"
        elif n_nf_v[i] == 0:
            f_state[i], f_detail[i] = "invalid", "flagged_by_module1"
        elif not has_sel[i]:
            f_state[i], f_detail[i] = "no_eligible", "all_versions_published_after_cutoff"
        elif sel_state[i] == "ok":
            pass
        elif sel_state[i] == "missing":
            f_state[i], f_detail[i] = "missing", "selected_version_has_null_value"
        else:
            f_state[i], f_detail[i] = "invalid", str(sel_state[i])
    a["forecast_state"] = f_state
    a["forecast_detail"] = f_detail
    a["forecast_mw"] = np.where(f_state == "ok", sel_value, np.nan)

    # ---- actual state -----------------------------------------------------------------
    ai = ares.set_index("interval_start_utc")
    a_any = _count_lookup(ai["n_rows_total"], keys)
    a_st = pd.Series(_lookup(ai["state"].astype(object), keys)).astype(object).to_numpy()
    a_val = pd.Series(_lookup(ai["value"], keys)).to_numpy(dtype="float64")
    a_collapsed = _count_lookup(ai["n_collapsed"], keys)
    a_state = np.full(len(a), "ok", dtype=object)
    a_detail = np.full(len(a), "", dtype=object)
    for i in range(len(a)):
        if a_any[i] == 0:
            a_state[i], a_detail[i] = "missing", "no_actual_record"
        elif a_st[i] == "flagged":
            a_state[i], a_detail[i] = "invalid", "flagged_by_module1"
        elif a_st[i] == "missing":
            a_state[i], a_detail[i] = "missing", "null_value"
        elif a_st[i] != "ok":
            a_state[i], a_detail[i] = "invalid", str(a_st[i])
    a["actual_state"] = a_state
    a["actual_detail"] = a_detail
    a["actual_mw"] = np.where(a_state == "ok", a_val, np.nan)

    # ---- single primary reason (mutually exclusive) + full issue list ----------------
    reasons, details, issues = [], [], []
    for fs, fd, as_, ad, late, fcol, acol in zip(
        f_state, f_detail, a_state, a_detail, a["late_version_count"], sel_collapsed, a_collapsed
    ):
        if fs == "missing" and as_ == "missing":
            r, d = "missing_forecast_and_actual", f"forecast:{fd};actual:{ad}"
        elif as_ == "missing":
            r, d = "missing_actual", ad
        elif fs == "missing":
            r, d = "missing_forecast", fd
        elif fs == "no_eligible":
            r, d = "no_eligible_forecast", fd
        elif fs == "invalid":
            r, d = "invalid_forecast", fd
        elif as_ == "invalid":
            r, d = "invalid_actual", ad
        else:
            r, d = REASON_VALID, ""
        iss = []
        if fs != "ok":
            iss.append(f"forecast:{fd}")
        if as_ != "ok":
            iss.append(f"actual:{ad}")
        if late:
            iss.append(f"info:{int(late)}_post_cutoff_version(s)_ignored")
        if fcol:
            iss.append(f"info:{int(fcol)}_duplicate_forecast_row(s)_collapsed")
        if acol:
            iss.append(f"info:{int(acol)}_duplicate_actual_row(s)_collapsed")
        reasons.append(r)
        details.append(d)
        issues.append(";".join(iss))
    a["reason"] = reasons
    a["reason_detail"] = details
    a["issues"] = issues
    a["is_valid"] = a["reason"].eq(REASON_VALID)
    a["lead_time_hours"] = (a["interval_start_utc"] - a["forecast_publish_time_utc"]).dt.total_seconds() / 3600.0
    a.loc[~a["is_valid"], "lead_time_hours"] = np.nan

    if has_m1_sel:
        both_nat = a["selected_publish_time_utc"].isna() & a["forecast_publish_time_utc"].isna()
        a["module1_selection_matches"] = (a["selected_publish_time_utc"] == a["forecast_publish_time_utc"]) | both_nat
        info["module1_selection_mismatches"] = int((~a["module1_selection_matches"]).sum())
    else:
        a["module1_selection_matches"] = pd.NA
        info["module1_selection_mismatches"] = None

    info["late_forecast_versions_ignored"] = int(a["late_version_count"].sum())

    audit_cols = [
        "interval_start_utc", "decision_cutoff_utc", "forecast_publish_time_utc", "lead_time_hours",
        "forecast_mw", "actual_mw", "is_valid", "reason", "reason_detail", "issues",
        "forecast_state", "actual_state", "forecast_version_count", "late_version_count",
        "module1_selection_matches",
    ]
    audit = a[audit_cols].copy()

    pairs = audit.loc[audit["is_valid"], [
        "interval_start_utc", "decision_cutoff_utc", "forecast_publish_time_utc",
        "lead_time_hours", "forecast_mw", "actual_mw",
    ]].reset_index(drop=True)

    # ---- versions table for forecast_comparison -------------------------------------
    vers = nf.copy()
    ai_state = pd.Series(a["actual_state"].to_numpy(), index=pd.Index(a["interval_start_utc"]))
    ai_val = pd.Series(a["actual_mw"].to_numpy(), index=pd.Index(a["interval_start_utc"]))
    ai_valid = pd.Series(a["is_valid"].to_numpy(), index=pd.Index(a["interval_start_utc"]))
    ai_sel = pd.Series(a["forecast_publish_time_utc"].array, index=pd.Index(a["interval_start_utc"]))
    vk = vers["interval_start_utc"]
    vers["actual_state"] = pd.Series(_lookup(ai_state, vk)).astype(object).to_numpy()
    vers["actual_mw"] = pd.Series(_lookup(ai_val, vk)).to_numpy(dtype="float64")
    vers["decision_pair_valid"] = pd.Series(_lookup(ai_valid, vk)).fillna(False).astype(bool).to_numpy()
    vers["is_decision_version"] = (vers["publish_time_utc"].to_numpy() == _lookup(ai_sel, vk).to_numpy()) if len(vers) else False
    vers = vers.rename(columns={"value": "forecast_mw", "state": "forecast_state"}).reset_index(drop=True)

    summary = _summarise(audit, info)
    return ValidationResult(
        config=cfg, intervals=audit, pairs=pairs, versions=vers, summary=summary,
        dataset_id=dataset.dataset_id, dataset_version=dataset.dataset_version,
    )


def _summarise(audit: pd.DataFrame, info: dict) -> dict:
    n = int(len(audit))
    counts = audit["reason"].value_counts().to_dict()
    c = {k: int(counts.get(k, 0)) for k in (REASON_VALID,) + EXCLUSION_REASONS}
    invalid_detail = (
        audit.loc[audit["reason"].isin(["invalid_forecast", "invalid_actual"])]
        .groupby(["reason", "reason_detail"]).size()
    )
    detail_counts = {f"{r}:{d}": int(v) for (r, d), v in invalid_detail.items()}
    summary = {
        "expected_intervals": n,
        "valid_matched_pairs": c[REASON_VALID],
        "missing_forecasts": c["missing_forecast"],
        "missing_actuals": c["missing_actual"],
        "missing_both": c["missing_forecast_and_actual"],
        "no_eligible_forecasts": c["no_eligible_forecast"],
        "invalid_pairs": c["invalid_forecast"] + c["invalid_actual"],
        "coverage_pct": (c[REASON_VALID] / n * 100.0) if n else None,
        "exclusions_by_reason": {k: c[k] for k in EXCLUSION_REASONS},
        "invalid_detail_counts": detail_counts,
        "informational": info,
    }
    assert summary["valid_matched_pairs"] + sum(summary["exclusions_by_reason"].values()) == n
    return summary
