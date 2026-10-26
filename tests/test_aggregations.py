"""Daily / time-of-day aggregation: grouping, timezone convention, sample counts."""
import numpy as np
import pandas as pd
import pytest

from module2.aggregations import daily_metrics, time_of_day_metrics
from module2.config import AnalyticsConfig
from module2.data_quality import validate
from tests.builders import make_dataset, simple_dataset


def _two_day_dataset(t0=None):
    # day 1: every error +10 ; day 2: every error -30   (48 intervals each)
    a = [1000.0] * 96
    f = [1010.0] * 48 + [970.0] * 48
    kw = {} if t0 is None else {"t0": t0}
    return simple_dataset(f, a, **kw)


def test_daily_values_and_counts_hand_checked():
    r = validate(_two_day_dataset())
    d = daily_metrics(r.intervals)
    assert d["group"].tolist() == ["2026-01-05", "2026-01-06"]
    assert d["sample_count"].tolist() == [48, 48] and d["expected_intervals"].tolist() == [48, 48]
    assert d["mae_mw"].tolist() == pytest.approx([10.0, 30.0])
    assert d["mbe_mw"].tolist() == pytest.approx([10.0, -30.0])
    assert d["rmse_mw"].tolist() == pytest.approx([10.0, 30.0])
    assert d["coverage_pct"].tolist() == [100.0, 100.0]


def test_day_with_no_valid_pairs_keeps_none_metrics_not_zero():
    f = [1010.0] * 48 + [None] * 48
    r = validate(simple_dataset(f, [1000.0] * 96))
    d = daily_metrics(r.intervals)
    day2 = d[d["group"] == "2026-01-06"].iloc[0]
    assert day2["sample_count"] == 0 and day2["expected_intervals"] == 48
    assert pd.isna(day2["mae_mw"]) and pd.isna(day2["rmse_mw"]) and pd.isna(day2["mbe_mw"])
    assert day2["coverage_pct"] == 0.0 and bool(day2["low_sample"])


def test_weighted_daily_equals_overall():
    r = validate(make_dataset(96))
    d = daily_metrics(r.intervals)
    n = d["sample_count"].to_numpy()
    assert (d["mae_mw"] * n).sum() / n.sum() == pytest.approx(35.0)
    assert (d["mbe_mw"] * n).sum() / n.sum() == pytest.approx(15.0)
    assert np.sqrt((d["rmse_mw"] ** 2 * n).sum() / n.sum()) == pytest.approx(np.sqrt(1450.0))


def test_time_of_day_buckets_and_counts():
    r = validate(_two_day_dataset())
    t = time_of_day_metrics(r.intervals, bucket_minutes=60)
    assert len(t) == 24 and t["group"].iloc[0] == "00:00" and t["group"].iloc[-1] == "23:00"
    assert (t["sample_count"] == 4).all() and (t["expected_intervals"] == 4).all()
    assert t["mae_mw"].tolist() == pytest.approx([20.0] * 24)       # (10+10+30+30)/4
    assert t["mbe_mw"].tolist() == pytest.approx([-10.0] * 24)       # (10+10-30-30)/4
    t30 = time_of_day_metrics(r.intervals, bucket_minutes=30)
    assert len(t30) == 48 and (t30["sample_count"] == 2).all()


@pytest.mark.parametrize("bad", [0, 7, 45, 25, -30, 15])
def test_invalid_bucket_width_rejected(bad):
    r = validate(_two_day_dataset())
    with pytest.raises(ValueError):
        time_of_day_metrics(r.intervals, bucket_minutes=bad)


def test_timezone_convention_changes_date_assignment_explicitly():
    # 2026-07-01T23:00Z is already 2026-07-02 00:00 in Europe/London (BST)
    t0 = pd.Timestamp("2026-07-01T23:00:00Z")
    r = validate(simple_dataset([100.0] * 2, [100.0] * 2, t0=t0))
    utc = daily_metrics(r.intervals, AnalyticsConfig(aggregation_timezone="UTC"))
    lon = daily_metrics(r.intervals, AnalyticsConfig(aggregation_timezone="Europe/London"))
    assert utc["group"].tolist() == ["2026-07-01"]
    assert lon["group"].tolist() == ["2026-07-02"]
    tod = time_of_day_metrics(r.intervals, AnalyticsConfig(aggregation_timezone="Europe/London"), 30)
    assert tod["group"].tolist() == ["00:00", "00:30"]


def test_dst_spring_forward_day_has_46_expected_intervals_in_london():
    t0 = pd.Timestamp("2026-03-29T00:00:00Z")     # clocks go forward at 01:00Z on this day
    r = validate(simple_dataset([1.0] * 96, [1.0] * 96, t0=t0))
    d = daily_metrics(r.intervals, AnalyticsConfig(aggregation_timezone="Europe/London"))
    assert d["group"].tolist() == ["2026-03-29", "2026-03-30", "2026-03-31"]
    assert d["expected_intervals"].tolist() == [46, 48, 2]


def test_low_sample_flag_and_empty_input():
    r = validate(simple_dataset([1.0, 2.0], [1.0, 2.0]))
    assert bool(daily_metrics(r.intervals)["low_sample"].iloc[0]) is True
    empty = daily_metrics(r.intervals.iloc[0:0])
    assert empty.empty and "mae_mw" in empty.columns
