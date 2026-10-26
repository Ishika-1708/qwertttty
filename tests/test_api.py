"""HTTP-level tests (require FastAPI + httpx; skipped automatically if not installed)."""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from module2.main import create_app  # noqa: E402
from module2.providers import FileDatasetProvider, InMemoryProvider  # noqa: E402
from tests.builders import make_dataset  # noqa: E402


def client(ds=None):
    return TestClient(create_app(InMemoryProvider(ds or make_dataset(96))))


def test_summary_endpoint_fields_and_types():
    r = client().get("/api/analytics/summary")
    assert r.status_code == 200
    j = r.json()
    assert set(j) == {"period", "metrics", "coverage", "unit", "error_sign_convention", "traceability"}
    assert j["metrics"]["sample_count"] == 96 and j["metrics"]["mae_mw"] == pytest.approx(35.0)
    assert isinstance(j["coverage"]["coverage_pct"], float) and j["unit"] == "MW"


def test_all_endpoints_return_200_and_share_fingerprint():
    c = client()
    paths = ["summary", "intervals", "daily", "forecast-versions", "data-quality"]
    fps = set()
    for p in paths:
        r = c.get(f"/api/analytics/{p}")
        assert r.status_code == 200, (p, r.text)
        fps.add(r.json()["traceability"]["pairs_fingerprint"])
    assert len(fps) == 1


def test_date_filter_and_validation_errors():
    c = client()
    j = c.get("/api/analytics/summary", params={"start_date": "2026-01-05", "end_date": "2026-01-05"}).json()
    assert j["metrics"]["sample_count"] == 48
    assert c.get("/api/analytics/summary", params={"start_date": "2026-01-06", "end_date": "2026-01-05"}).status_code == 422
    assert c.get("/api/analytics/summary", params={"start_date": "not-a-date"}).status_code == 422
    assert c.get("/api/analytics/intervals", params={"status": "nope"}).status_code == 422
    assert c.get("/api/analytics/intervals", params={"limit": 0}).status_code == 422
    assert c.get("/api/analytics/daily", params={"group_by": "time_of_day", "bucket_minutes": 7}).status_code == 422
    assert c.get("/api/analytics/forecast-versions", params={"lead_bins": "a,b"}).status_code == 422


def test_empty_results_are_200_with_nulls_not_errors():
    c = client()
    p = {"start_date": "2030-01-01", "end_date": "2030-01-02"}
    s = c.get("/api/analytics/summary", params=p)
    assert s.status_code == 200 and s.json()["metrics"]["mae_mw"] is None and s.json()["metrics"]["sample_count"] == 0
    assert c.get("/api/analytics/intervals", params=p).json()["items"] == []
    assert c.get("/api/analytics/daily", params=p).json()["groups"] == []
    assert c.get("/api/analytics/forecast-versions", params=p).json()["revision_analysis"]["status"] == "no_eligible_data"


def test_dashboard_numbers_match_backend_over_http():
    c = client()
    summ = c.get("/api/analytics/summary").json()["metrics"]
    items = c.get("/api/analytics/intervals", params={"limit": 10000}).json()["items"]
    assert sum(abs(i["error_mw"]) for i in items) / len(items) == pytest.approx(summ["mae_mw"])
    groups = c.get("/api/analytics/daily").json()["groups"]
    assert sum(g["sample_count"] for g in groups) == summ["sample_count"]


def test_missing_module1_dataset_gives_503():
    c = TestClient(create_app(FileDatasetProvider("/definitely/not/here")))
    assert c.get("/api/analytics/summary").status_code == 503


def test_contract_violation_from_module1_gives_502():
    ds = make_dataset(4)
    ds.actuals["interval_start_utc"] = ds.actuals["interval_start_utc"].dt.tz_localize(None)   # naive timestamps
    assert client(ds).get("/api/analytics/summary").status_code == 502


def test_openapi_documents_all_five_endpoints():
    paths = client().get("/openapi.json").json()["paths"]
    for p in ("summary", "intervals", "daily", "forecast-versions", "data-quality"):
        assert f"/api/analytics/{p}" in paths
