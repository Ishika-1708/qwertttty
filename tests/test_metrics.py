"""Unit tests for metrics.py - hand-verifiable inputs, numerical tolerance."""
import numpy as np
import pandas as pd
import pytest

from module2.data_quality import validate
from module2.metrics import add_error_columns, compute_metrics, metrics_from_pairs, signed_errors
from tests.builders import simple_dataset

TOL = 1e-9


def test_worked_example_from_brief():
    # errors +1500, -500, +1000 MW  (F - A)
    a = [10000.0, 10000.0, 10000.0]
    f = [11500.0, 9500.0, 11000.0]
    e, abs_e = signed_errors(f, a)
    assert e.tolist() == [1500.0, -500.0, 1000.0]
    assert abs_e.tolist() == [1500.0, 500.0, 1000.0]
    m = compute_metrics(f, a)
    assert m.sample_count == 3
    assert m.mae_mw == pytest.approx(1000.0, abs=TOL)
    assert m.rmse_mw == pytest.approx(1080.12, abs=0.005)       # sqrt(3.5e6/3) = 1080.1234...
    assert m.rmse_mw == pytest.approx((3.5e6 / 3) ** 0.5, abs=TOL)
    assert m.mbe_mw == pytest.approx(666.6666666667, abs=1e-6)


def test_second_worked_example():
    f, a = [100, 120, 90], [110, 100, 100]
    e, _ = signed_errors(f, a)
    assert e.tolist() == [-10.0, 20.0, -10.0]
    m = compute_metrics(f, a)
    assert m.mae_mw == pytest.approx(13.3333333, abs=1e-6)
    assert m.rmse_mw == pytest.approx(14.1421356, abs=1e-6)     # sqrt(200)
    assert m.mbe_mw == pytest.approx(0.0, abs=TOL)


def test_worked_examples_through_full_pipeline():
    r = validate(simple_dataset([11500, 9500, 11000], [10000, 10000, 10000]))
    m = metrics_from_pairs(r.pairs)
    assert (m.sample_count, m.mae_mw) == (3, pytest.approx(1000.0))
    assert m.rmse_mw == pytest.approx(1080.1234, abs=1e-3)
    assert m.mbe_mw == pytest.approx(666.6667, abs=1e-3)


def test_all_forecasts_equal_actuals_gives_zero_metrics():
    m = compute_metrics([5, 6, 7], [5, 6, 7])
    assert (m.mae_mw, m.rmse_mw, m.mbe_mw) == (0.0, 0.0, 0.0)
    assert m.sample_count == 3


def test_no_samples_returns_none_not_zero():
    m = compute_metrics([], [])
    assert m.sample_count == 0
    assert m.mae_mw is None and m.rmse_mw is None and m.mbe_mw is None


def test_single_pair():
    m = compute_metrics([90.0], [100.0])
    assert m.sample_count == 1
    assert m.mae_mw == 10.0 and m.rmse_mw == 10.0 and m.mbe_mw == -10.0


def test_cancellation_in_mbe_but_not_mae():
    m = compute_metrics([110.0, 90.0], [100.0, 100.0])          # +10, -10
    assert m.mbe_mw == pytest.approx(0.0, abs=TOL)
    assert m.mae_mw == 10.0 and m.mae_mw >= 0
    assert m.rmse_mw == pytest.approx(10.0)


def test_sign_convention_overforecast_positive():
    e, _ = signed_errors([120.0], [100.0])
    assert e[0] == 20.0
    e, _ = signed_errors([80.0], [100.0])
    assert e[0] == -20.0


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf, None])
def test_non_finite_input_is_refused_not_zero_filled(bad):
    with pytest.raises(ValueError):
        compute_metrics([1.0, bad], [1.0, 2.0])
    with pytest.raises(ValueError):
        compute_metrics([1.0, 2.0], [1.0, bad])


def test_length_mismatch_rejected():
    with pytest.raises(ValueError):
        compute_metrics([1.0, 2.0], [1.0])


def test_mape_excludes_small_actuals_and_reports_count():
    m = compute_metrics([110.0, 5.0, 220.0], [100.0, 0.0, 200.0], include_mape=True, mape_min_actual_mw=100.0)
    assert m.mape_sample_count == 2 and m.mape_excluded_count == 1
    assert m.mape_pct == pytest.approx(10.0)                    # (10/100 + 20/200)/2 * 100
    # MAE/RMSE/MBE still use ALL three pairs (MAPE exclusion never changes them)
    assert m.sample_count == 3
    assert m.mae_mw == pytest.approx((10 + 5 + 20) / 3)


def test_mape_none_when_no_eligible_actuals_and_off_by_default():
    m = compute_metrics([1.0], [0.0], include_mape=True)
    assert m.mape_pct is None and m.mape_sample_count == 0 and m.mape_excluded_count == 1
    assert compute_metrics([1.0], [0.0]).mape_pct is None


def test_add_error_columns_masks_with_nan_not_zero():
    df = pd.DataFrame({"forecast_mw": [10.0, np.nan], "actual_mw": [4.0, np.nan]})
    out = add_error_columns(df, mask=pd.Series([True, False]))
    assert out.loc[0, "error_mw"] == 6.0 and out.loc[0, "abs_error_mw"] == 6.0
    assert np.isnan(out.loc[1, "error_mw"]) and np.isnan(out.loc[1, "abs_error_mw"])
