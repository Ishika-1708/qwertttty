"""Integration: Module 1 standardized dataset -> Module 2 service payloads (the exact dicts the API serialises).

Runs without FastAPI so the whole analytic path is testable anywhere. Includes the
'dashboard agrees with backend' checks: every figure a dashboard could display is
reproducible from backend payloads without any client-side MAE/RMSE logic.
"""
import json
import math
import tempfile
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from module2.providers import FileDatasetProvider
from module2.service import AnalyticsService
from tests.builders import make_dataset, simple_dataset

D1, D2 = date(2026, 1, 5), date(2026, 1, 6)


def svc(ds=None):
    return AnalyticsService(ds or make_dataset(96))


def all_intervals(s, **kw):
    items, off = [], 0
    while True:
        page = s.intervals(limit=50, offset=off, **kw)
        items += page["items"]
        off += 50
        if off >= page["total"]:
            return items, page


def no_nan(payload):
    json.dumps(payload, allow_nan=False)        # raises on NaN/Infinity -> guarantees clean JSON


# ------------------------------------------------------------------ end to end
def test_summary_known_answer_and_traceability():
    p = svc().summary()
    m = p["metrics"]
    assert m["sample_count"] == 96
    assert m["mae_mw"] == pytest.approx(35.0) and m["mbe_mw"] == pytest.approx(15.0)
    assert m["rmse_mw"] == pytest.approx(math.sqrt(1450.0))
    assert p["coverage"]["coverage_pct"] == 100.0 and p["unit"] == "MW"
    t = p["traceability"]
    assert t["dataset_id"] == "synthetic" and t["calculation_version"] and len(t["pairs_fingerprint"]) == 16
    assert "<= decision_cutoff_utc" in t["forecast_selection_rule"]
    assert t["input_row_counts"] == {"forecast_rows": 384, "actual_rows": 96, "expected_intervals": 96}
    no_nan(p)


def test_dashboard_displayed_metrics_agree_with_backend_calculations():
    s = svc()
    summ = s.summary()
    items, _ = all_intervals(s)
    # (1) interval-level values reproduce the headline numbers
    err = np.array([i["error_mw"] for i in items])
    assert len(items) == summ["metrics"]["sample_count"]
    assert np.abs(err).mean() == pytest.approx(summ["metrics"]["mae_mw"])
    assert err.mean() == pytest.approx(summ["metrics"]["mbe_mw"])
    assert math.sqrt((err ** 2).mean()) == pytest.approx(summ["metrics"]["rmse_mw"])
    assert all(i["error_mw"] == pytest.approx(i["forecast_mw"] - i["actual_mw"]) for i in items)
    assert all(i["abs_error_mw"] == abs(i["error_mw"]) for i in items)
    # (2) daily groups recombine to the headline numbers
    g = s.aggregation()["groups"]
    n = np.array([x["sample_count"] for x in g], float)
    assert (np.array([x["mae_mw"] for x in g]) * n).sum() / n.sum() == pytest.approx(summ["metrics"]["mae_mw"])
    assert (np.array([x["mbe_mw"] for x in g]) * n).sum() / n.sum() == pytest.approx(summ["metrics"]["mbe_mw"])
    # (3) decision-time block of /forecast-versions == /summary
    fv = s.forecast_versions()
    assert fv["decision_time_evaluation"]["metrics"] == {**summ["metrics"]}
    # (4) same pairs everywhere
    fps = {summ["traceability"]["pairs_fingerprint"], s.intervals()["traceability"]["pairs_fingerprint"],
           s.aggregation()["traceability"]["pairs_fingerprint"], fv["traceability"]["pairs_fingerprint"],
           s.data_quality()["traceability"]["pairs_fingerprint"]}
    assert len(fps) == 1


def test_data_quality_counts_consistent_with_summary_and_intervals():
    ds = make_dataset(96)
    ds.actuals.loc[ds.actuals.index[:6], "actual_mw"] = None            # 6 missing actuals
    ds.forecasts = ds.forecasts[~((ds.forecasts["interval_start_utc"] == ds.actuals["interval_start_utc"].iloc[10]))]  # 1 missing forecast
    s = svc(ds)
    dq, summ = s.data_quality(), s.summary()
    assert dq["coverage"] == summ["coverage"]
    c = dq["coverage"]
    assert c["expected_intervals"] == 96 and c["missing_actuals"] == 6 and c["missing_forecasts"] == 1
    assert c["valid_matched_pairs"] == 89 and c["coverage_pct"] == pytest.approx(89 / 96 * 100)
    assert c["valid_matched_pairs"] + sum(dq["exclusions_by_reason"].values()) == c["expected_intervals"]
    excl = s.intervals(status="excluded")
    assert excl["total"] == 7 and all(i["status"] == "excluded" and i["error_mw"] is None for i in excl["items"])
    assert s.intervals(status="all")["total"] == 96
    assert {i["exclusion_reason"] for i in excl["items"]} == {"missing_actual", "missing_forecast"}
    assert len(dq["excluded_examples"]) == 7
    no_nan(dq)


# ------------------------------------------------------------------ filters / params
def test_date_filters_behave_as_documented():
    s = svc()
    one = s.summary(D1, D1)
    assert one["coverage"]["expected_intervals"] == 48 and one["metrics"]["sample_count"] == 48
    assert one["period"]["start_date"] == "2026-01-05" and one["period"]["first_interval_utc"] == "2026-01-05T00:00:00Z"
    assert one["period"]["last_interval_utc"] == "2026-01-05T23:30:00Z"
    assert s.summary(D2, None)["metrics"]["sample_count"] == 48
    assert s.summary(None, D1)["metrics"]["sample_count"] == 48
    assert [g["group"] for g in s.aggregation(D1, D2)["groups"]] == ["2026-01-05", "2026-01-06"]
    with pytest.raises(ValueError):
        s.summary(D2, D1)


def test_intervals_pagination_and_status_validation():
    s = svc()
    p = s.intervals(limit=10, offset=90)
    assert p["total"] == 96 and len(p["items"]) == 6
    assert s.intervals(limit=10)["items"][0]["interval_start_utc"] == "2026-01-05T00:00:00Z"
    with pytest.raises(ValueError):
        s.intervals(status="bogus")
    with pytest.raises(ValueError):
        s.intervals(limit=0)


def test_local_time_display_is_explicit_and_separate_from_grouping():
    s = AnalyticsService(simple_dataset([1.0], [1.0], t0=__import__("pandas").Timestamp("2026-07-01T23:00:00Z")))
    item = s.intervals()["items"][0]
    assert item["interval_start_utc"] == "2026-07-01T23:00:00Z"
    assert item["interval_start_local"] == "2026-07-02T00:00:00+01:00"
    assert s.aggregation()["groups"][0]["group"] == "2026-07-01"        # grouping stays on aggregation tz (UTC)


def test_time_of_day_grouping_payload():
    p = svc().aggregation(group_by="time_of_day", bucket_minutes=120)
    assert p["group_by"] == "time_of_day" and p["bucket_minutes"] == 120 and len(p["groups"]) == 12
    assert "do not establish a cause" in p["note"]
    with pytest.raises(ValueError):
        svc().aggregation(group_by="time_of_day", bucket_minutes=7)
    with pytest.raises(ValueError):
        svc().aggregation(group_by="month")


# ------------------------------------------------------------------ empty results
def test_empty_result_set_everywhere():
    s = svc()
    far = date(2030, 1, 1)
    summ = s.summary(far, far)
    assert summ["metrics"]["sample_count"] == 0
    assert summ["metrics"]["mae_mw"] is None and summ["metrics"]["rmse_mw"] is None and summ["metrics"]["mbe_mw"] is None
    assert summ["coverage"]["expected_intervals"] == 0 and summ["coverage"]["coverage_pct"] is None
    assert summ["period"]["first_interval_utc"] is None
    iv = s.intervals(far, far)
    assert iv["total"] == 0 and iv["items"] == []
    assert s.aggregation(far, far)["groups"] == []
    assert s.aggregation(far, far, group_by="time_of_day")["groups"] == []
    fv = s.forecast_versions(far, far)
    assert fv["revision_analysis"]["status"] == "no_eligible_data"
    assert fv["decision_time_evaluation"]["metrics"]["mae_mw"] is None
    dq = s.data_quality(far, far)
    assert dq["coverage"]["expected_intervals"] == 0 and dq["excluded_examples"] == []
    for payload in (summ, iv, fv, dq):
        no_nan(payload)


def test_all_actuals_missing_end_to_end():
    ds = make_dataset(48)
    ds.actuals["actual_mw"] = None
    p = svc(ds).summary()
    assert p["metrics"]["sample_count"] == 0 and p["metrics"]["mae_mw"] is None
    assert p["coverage"]["missing_actuals"] == 48 and p["coverage"]["coverage_pct"] == 0.0
    no_nan(p)


def test_forecast_versions_payload_separates_decision_and_revision():
    p = svc().forecast_versions(include_mape=True)
    assert set(p) >= {"decision_time_evaluation", "revision_analysis"}
    assert p["decision_time_evaluation"]["metrics"]["mape_pct"] is not None
    ra = p["revision_analysis"]
    assert ra["status"] == "ok" and ra["include_post_cutoff"] is False
    assert all(b["scope"] == "pre_cutoff" for b in ra["by_lead_bucket"])
    no_nan(p)


def test_response_field_types_are_stable():
    s = svc()
    m = s.summary()["metrics"]
    assert isinstance(m["sample_count"], int) and isinstance(m["mae_mw"], float)
    row = s.aggregation()["groups"][0]
    assert isinstance(row["group"], str) and isinstance(row["low_sample"], bool) and isinstance(row["sample_count"], int)
    item = s.intervals(limit=1)["items"][0]
    assert isinstance(item["forecast_mw"], float) and isinstance(item["status"], str)


# ------------------------------------------------------------------ Module 1 hand-off
def test_file_provider_roundtrip_matches_in_memory_result():
    ds = make_dataset(96)
    with tempfile.TemporaryDirectory() as d:
        ds.expected_intervals.to_csv(Path(d) / "expected_intervals.csv", index=False)
        ds.forecasts.to_csv(Path(d) / "forecasts.csv", index=False)
        ds.actuals.to_csv(Path(d) / "actuals.csv", index=False)
        loaded = FileDatasetProvider(d).get_dataset()
        a, b = AnalyticsService(ds).summary(), AnalyticsService(loaded).summary()
    assert a["metrics"] == b["metrics"] and a["coverage"] == b["coverage"]
    assert a["traceability"]["pairs_fingerprint"] == b["traceability"]["pairs_fingerprint"]
