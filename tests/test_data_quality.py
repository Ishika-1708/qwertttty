"""Validation rules, exclusion accounting, deduplication, cutoff eligibility."""
import numpy as np
import pandas as pd
import pytest

from module2.config import AnalyticsConfig
from module2.contract import Module1Dataset, SchemaError
from module2.data_quality import EXCLUSION_REASONS, validate
from module2.metrics import metrics_from_pairs
from tests.builders import (
    CUTOFF_LEAD_H, T0, _ts, empty_actuals, empty_forecasts, expected_frame, make_dataset, simple_dataset,
)


def reasons(r):
    return r.intervals["reason"].tolist()


def assert_partition(r):
    s = r.summary
    assert s["valid_matched_pairs"] + sum(s["exclusions_by_reason"].values()) == s["expected_intervals"]
    assert set(s["exclusions_by_reason"]) == set(EXCLUSION_REASONS)
    assert s["valid_matched_pairs"] == len(r.pairs)


# ------------------------------------------------------------------ missing data
def test_all_actuals_missing_metrics_unavailable():
    r = validate(simple_dataset([100.0, 110.0, 120.0], [None, None, None]))
    m = metrics_from_pairs(r.pairs)
    assert m.sample_count == 0 and m.mae_mw is None and m.rmse_mw is None and m.mbe_mw is None
    assert r.summary["missing_actuals"] == 3 and r.summary["coverage_pct"] == 0.0
    assert_partition(r)


def test_no_actual_rows_at_all():
    ds = simple_dataset([100.0, 110.0], [1.0, 2.0])
    ds.actuals = empty_actuals()
    r = validate(ds)
    assert reasons(r) == ["missing_actual"] * 2 and len(r.pairs) == 0


def test_missing_forecast_is_not_treated_as_zero():
    # actual 0.0 with a null forecast would give error 0 if None were zero-filled
    r = validate(simple_dataset([None, 100.0], [0.0, 100.0]))
    assert reasons(r) == ["missing_forecast", "valid"]
    assert len(r.pairs) == 1
    ds = simple_dataset([100.0], [50.0])
    ds.forecasts = empty_forecasts()
    assert reasons(validate(ds)) == ["missing_forecast"]


def test_both_missing_counted_once():
    r = validate(simple_dataset([None, 1.0], [None, 1.0]))
    assert reasons(r) == ["missing_forecast_and_actual", "valid"]
    assert r.summary["missing_both"] == 1
    assert r.summary["missing_forecasts"] == 0 and r.summary["missing_actuals"] == 0   # not double counted
    assert_partition(r)


def test_one_matched_pair_only():
    r = validate(simple_dataset([105.0], [100.0]))
    m = metrics_from_pairs(r.pairs)
    assert (m.sample_count, m.mae_mw, m.rmse_mw, m.mbe_mw) == (1, 5.0, 5.0, 5.0)
    assert r.summary["coverage_pct"] == 100.0


# ------------------------------------------------------------------ cutoff
def test_forecast_published_after_cutoff_is_not_eligible():
    ds = simple_dataset([100.0, 100.0], [100.0, 100.0], publish_before_cutoff_h=-1.0)   # 1h AFTER cutoff
    r = validate(ds)
    assert reasons(r) == ["no_eligible_forecast"] * 2
    assert r.summary["no_eligible_forecasts"] == 2 and len(r.pairs) == 0
    assert r.intervals["forecast_mw"].isna().all()                                       # not used, not zero
    assert_partition(r)


def test_forecast_published_exactly_at_cutoff_is_eligible():
    r = validate(simple_dataset([100.0], [90.0], publish_before_cutoff_h=0.0))
    assert reasons(r) == ["valid"] and r.pairs["forecast_mw"].iloc[0] == 100.0


def test_late_version_never_replaces_eligible_version():
    r = validate(make_dataset(4))
    # decision forecasts are A+50 / A-20 alternating; the late version (== A) must be ignored
    assert r.pairs["forecast_mw"].tolist() == [5050.0, 5000 + 10 - 20, 5020 + 50, 5030 - 20]
    assert r.intervals["late_version_count"].tolist() == [1, 1, 1, 1]
    assert metrics_from_pairs(r.pairs).mae_mw == pytest.approx(35.0)


# ------------------------------------------------------------------ duplicates
def test_exact_duplicate_actuals_collapse_to_one_pair():
    ds = simple_dataset([100.0, 100.0], [90.0, 90.0])
    ds.actuals = pd.concat([ds.actuals, ds.actuals.iloc[[0]]], ignore_index=True)
    r = validate(ds)
    assert reasons(r) == ["valid", "valid"] and len(r.pairs) == 2
    assert r.summary["informational"]["duplicate_actual_rows_collapsed"] == 1


def test_conflicting_duplicate_actuals_are_rejected_not_guessed():
    ds = simple_dataset([100.0, 100.0], [90.0, 90.0])
    dup = ds.actuals.iloc[[0]].copy()
    dup["actual_mw"] = 95.0
    ds.actuals = pd.concat([ds.actuals, dup], ignore_index=True)
    r = validate(ds)
    assert reasons(r) == ["invalid_actual", "valid"]
    assert r.intervals["reason_detail"].iloc[0] == "ambiguous_duplicate"
    assert_partition(r)


def test_conflicting_duplicate_forecasts_same_publish_time_rejected():
    ds = simple_dataset([100.0], [90.0])
    dup = ds.forecasts.copy()
    dup["forecast_mw"] = 101.0
    ds.forecasts = pd.concat([ds.forecasts, dup], ignore_index=True)
    r = validate(ds)
    assert reasons(r) == ["invalid_forecast"] and r.intervals["reason_detail"].iloc[0] == "ambiguous_duplicate"


def test_flagged_duplicate_copy_is_dropped_and_ok_copy_used():
    ds = simple_dataset([100.0], [90.0])
    dup = ds.actuals.copy()
    dup["actual_mw"] = 999.0
    dup["quality_flag"] = "DUPLICATE"
    ds.actuals = pd.concat([ds.actuals, dup], ignore_index=True)
    r = validate(ds)
    assert reasons(r) == ["valid"] and r.pairs["actual_mw"].iloc[0] == 90.0


def test_duplicate_expected_intervals_rejected():
    ds = simple_dataset([1.0, 1.0], [1.0, 1.0])
    ds.expected_intervals = pd.concat([ds.expected_intervals, ds.expected_intervals.iloc[[0]]], ignore_index=True)
    with pytest.raises(SchemaError):
        validate(ds)


# ------------------------------------------------------------------ invalid numbers
@pytest.mark.parametrize("bad,detail", [(np.inf, "non_finite"), (-np.inf, "non_finite"), ("abc", "non_numeric"), (-5.0, "negative")])
def test_invalid_forecast_values_excluded(bad, detail):
    r = validate(simple_dataset([bad, 100.0], [100.0, 100.0]))
    assert reasons(r) == ["invalid_forecast", "valid"]
    assert r.intervals["reason_detail"].iloc[0] == detail
    assert r.summary["invalid_pairs"] == 1 and len(r.pairs) == 1
    assert_partition(r)


@pytest.mark.parametrize("bad,detail", [(np.inf, "non_finite"), ("n/a", "non_numeric"), (-1.0, "negative")])
def test_invalid_actual_values_excluded(bad, detail):
    r = validate(simple_dataset([100.0, 100.0], [bad, 100.0]))
    assert reasons(r) == ["invalid_actual", "valid"]
    assert r.intervals["reason_detail"].iloc[0] == detail


def test_nan_is_missing_not_invalid_and_not_zero():
    r = validate(simple_dataset([np.nan], [10.0]))
    assert reasons(r) == ["missing_forecast"]


def test_negative_allowed_when_configured():
    r = validate(simple_dataset([-5.0], [-3.0]), AnalyticsConfig(allow_negative_values=True))
    assert reasons(r) == ["valid"]


def test_unit_mismatch_excluded_without_conversion():
    ds = simple_dataset([100.0, 100.0], [100.0, 100.0])
    ds.forecasts.loc[0, "unit"] = "kW"
    r = validate(ds)
    assert reasons(r) == ["invalid_forecast", "valid"]
    assert r.intervals["reason_detail"].iloc[0] == "unit_mismatch"


def test_module1_invalid_flag_excludes_record():
    ds = simple_dataset([100.0, 100.0], [100.0, 100.0])
    ds.forecasts.loc[0, "quality_flag"] = "INVALID"
    ds.actuals.loc[1, "quality_flag"] = "INVALID"
    r = validate(ds)
    assert reasons(r) == ["invalid_forecast", "invalid_actual"]
    assert set(r.intervals["reason_detail"]) == {"flagged_by_module1"}


def test_multiple_issues_on_one_interval_counted_once_with_precedence():
    # forecast is inf (invalid) AND actual is missing -> ONE primary reason: missing_actual
    r = validate(simple_dataset([np.inf, 1.0], [None, 1.0]))
    assert reasons(r) == ["missing_actual", "valid"]
    issues = r.intervals["issues"].iloc[0]
    assert "forecast:non_finite" in issues and "actual:null_value" in issues      # both still traceable
    assert_partition(r)


def test_mixed_defects_partition_invariant():
    f = [1.0, None, np.inf, 4.0, 5.0, None, "x", 8.0]
    a = [1.0, 2.0, None, None, 5.0, None, 7.0, -1.0]
    r = validate(simple_dataset(f, a, publish_before_cutoff_h=1.0))
    r.intervals  # noqa
    assert_partition(r)
    assert r.summary["expected_intervals"] == 8
    assert reasons(r) == ["valid", "missing_forecast", "missing_actual", "missing_actual", "valid",
                          "missing_forecast_and_actual", "invalid_forecast", "invalid_actual"]


# ------------------------------------------------------------------ schema / misc
def test_naive_timestamps_rejected():
    ds = simple_dataset([1.0], [1.0])
    ds.actuals["interval_start_utc"] = ds.actuals["interval_start_utc"].dt.tz_localize(None)
    with pytest.raises(SchemaError):
        validate(ds)


def test_missing_required_column_rejected():
    ds = simple_dataset([1.0], [1.0])
    ds.forecasts = ds.forecasts.drop(columns=["publish_time_utc"])
    with pytest.raises(SchemaError):
        validate(ds)


def test_records_for_unexpected_intervals_are_ignored_and_counted():
    ds = simple_dataset([1.0], [1.0])
    extra = ds.actuals.copy()
    extra["interval_start_utc"] = extra["interval_start_utc"] + pd.Timedelta(days=30)
    ds.actuals = pd.concat([ds.actuals, extra], ignore_index=True)
    r = validate(ds)
    assert r.summary["informational"]["unexpected_actual_rows"] == 1
    assert r.summary["expected_intervals"] == 1


def test_empty_expected_gives_none_coverage():
    ds = Module1Dataset(expected_frame(0), empty_forecasts(), empty_actuals())
    r = validate(ds)
    assert r.summary["expected_intervals"] == 0 and r.summary["coverage_pct"] is None
    assert len(r.pairs) == 0


def test_module1_selection_crosscheck_counts_mismatches_but_does_not_override():
    ds = make_dataset(4)
    sel = ds.expected_intervals["decision_cutoff_utc"].copy()          # == the 12h version we select
    sel.iloc[1] = sel.iloc[1] - pd.Timedelta(hours=12)                 # Module 1 claims the 24h version
    ds.expected_intervals["selected_publish_time_utc"] = sel
    r = validate(ds)
    assert r.summary["informational"]["module1_selection_mismatches"] == 1
    assert len(r.pairs) == 4                                           # Module 2's own selection still used


def test_coverage_formula():
    r = validate(simple_dataset([1.0, None, 3.0, 4.0], [1.0, 2.0, 3.0, 4.0]))
    assert r.summary["coverage_pct"] == pytest.approx(75.0)


def test_fingerprint_changes_with_pairs():
    a = validate(simple_dataset([1.0, 2.0], [1.0, 2.0])).fingerprint
    b = validate(simple_dataset([1.0, 3.0], [1.0, 2.0])).fingerprint
    assert a != b and a == validate(simple_dataset([1.0, 2.0], [1.0, 2.0])).fingerprint
