"""Decision-time evaluation vs revision analysis; cutoff handling; history availability."""
import pytest

from module2.data_quality import validate
from module2.forecast_comparison import compare_versions, decision_time_evaluation, revision_analysis
from module2.metrics import metrics_from_pairs
from tests.builders import empty_actuals, empty_forecasts, make_dataset, simple_dataset


def test_decision_time_uses_only_pre_cutoff_version():
    r = validate(make_dataset(96))
    d = decision_time_evaluation(r)["metrics"]
    assert d["mae_mw"] == pytest.approx(35.0) and d["mbe_mw"] == pytest.approx(15.0)
    # if the post-cutoff version (error 0) had leaked in, MAE would be < 35


def test_revision_buckets_known_values():
    r = validate(make_dataset(96))
    ra = revision_analysis(r)
    assert ra["status"] == "ok"
    by = {(x["scope"], x["lead_bucket"]): x for x in ra["by_lead_bucket"]}
    assert set(by) == {("pre_cutoff", "12-24h"), ("pre_cutoff", "24-48h"), ("pre_cutoff", "48-96h")}
    assert by[("pre_cutoff", "12-24h")]["mae_mw"] == pytest.approx(35.0)     # == decision-time MAE
    assert by[("pre_cutoff", "24-48h")]["mae_mw"] == pytest.approx(100.0)
    assert by[("pre_cutoff", "48-96h")]["mbe_mw"] == pytest.approx(300.0)
    assert all(x["version_count"] == 96 for x in ra["by_lead_bucket"])


def test_revision_summary_first_vs_decision_version():
    ra = revision_analysis(validate(make_dataset(96)))["revisions"]
    assert ra["intervals_with_multiple_versions"] == 96
    assert ra["mean_abs_error_first_mw"] == pytest.approx(300.0)
    assert ra["mean_abs_error_decision_mw"] == pytest.approx(35.0)
    assert ra["improved_count"] == 96 and ra["worsened_count"] == 0 and ra["unchanged_count"] == 0
    assert ra["mean_signed_revision_mw"] == pytest.approx(-285.0)             # 15 - 300


def test_post_cutoff_versions_only_in_separate_scope_and_never_in_decision_metrics():
    r = validate(make_dataset(96))
    ra = revision_analysis(r, include_post_cutoff=True)
    post = [x for x in ra["by_lead_bucket"] if x["scope"] == "post_cutoff"]
    assert len(post) == 1 and post[0]["mae_mw"] == pytest.approx(0.0) and post[0]["version_count"] == 96
    both = compare_versions(r, include_post_cutoff=True)
    assert both["decision_time_evaluation"]["metrics"]["mae_mw"] == pytest.approx(35.0)   # unchanged
    assert both["revision_analysis"]["revisions"]["mean_abs_error_decision_mw"] == pytest.approx(35.0)


def test_history_unavailable_when_only_selected_forecast_supplied():
    r = validate(simple_dataset([10.0, 20.0], [11.0, 21.0]))
    ra = revision_analysis(r)
    assert ra["status"] == "history_unavailable"
    assert ra["by_lead_bucket"] == [] and ra["revisions"] is None
    assert "every published version" in ra["message"]
    assert decision_time_evaluation(r)["metrics"]["sample_count"] == 2          # decision-time still works


def test_no_eligible_versions_reports_no_data_instead_of_inventing():
    r = validate(simple_dataset([10.0, 20.0], [10.0, 20.0], publish_before_cutoff_h=-2.0))
    ra = revision_analysis(r)
    assert ra["status"] == "no_eligible_data" and ra["by_lead_bucket"] == [] and ra["revisions"] is None
    m = decision_time_evaluation(r)["metrics"]
    assert m["sample_count"] == 0 and m["mae_mw"] is None and m["rmse_mw"] is None and m["mbe_mw"] is None


def test_no_forecast_or_actual_rows_at_all():
    ds = simple_dataset([1.0], [1.0])
    ds.forecasts, ds.actuals = empty_forecasts(), empty_actuals()
    assert revision_analysis(validate(ds))["status"] == "no_eligible_data"


def test_intervals_without_valid_actual_are_outside_revision_cohort():
    ds = make_dataset(96)
    ds.actuals.loc[ds.actuals.index[:10], "actual_mw"] = None
    r = validate(ds)
    ra = revision_analysis(r)
    assert r.summary["valid_matched_pairs"] == 86
    assert {x["interval_count"] for x in ra["by_lead_bucket"]} == {86}


def test_custom_lead_bins_and_validation():
    r = validate(make_dataset(8))
    ra = revision_analysis(r, lead_bins_hours=[0, 18, 60])
    assert {x["lead_bucket"] for x in ra["by_lead_bucket"]} == {"0-18h", "18-60h"}
    with pytest.raises(ValueError):
        revision_analysis(r, lead_bins_hours=[24, 6])
    with pytest.raises(ValueError):
        revision_analysis(r, lead_bins_hours=[6])
