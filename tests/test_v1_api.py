"""Integration tests for the dashboard V1 API endpoints."""
import pytest
from starlette.testclient import TestClient

from backend.main import create_app
from backend.providers import FileDatasetProvider


@pytest.fixture
def client():
    app = create_app(provider=FileDatasetProvider("output"))
    return TestClient(app)


def test_v1_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "calculation_version" in data


def test_v1_summary(client):
    r = client.get("/api/v1/metrics/summary?start=2026-01-01&end=2026-01-31")
    assert r.status_code == 200
    data = r.json()
    assert data["unit"] == "MW"
    assert data["expected_intervals"] == 1488
    assert data["valid_matched_intervals"] == 744
    assert data["coverage_pct"] == 50.0
    assert data["metrics"]["mae"] is not None
    assert data["metrics"]["rmse"] is not None
    assert data["metrics"]["mbe"] is not None


def test_v1_intervals(client):
    r = client.get("/api/v1/intervals?start=2026-01-01&end=2026-01-02")
    assert r.status_code == 200
    data = r.json()
    assert "intervals" in data
    assert len(data["intervals"]) > 0
    first = data["intervals"][0]
    assert "delivery_time" in first
    assert "forecast_mw" in first
    assert "actual_mw" in first
    assert "status" in first


def test_v1_daily(client):
    r = client.get("/api/v1/metrics/daily?start=2026-01-01&end=2026-01-31")
    assert r.status_code == 200
    data = r.json()
    assert "points" in data
    assert len(data["points"]) == 31
    assert data["points"][0]["mae"] is not None


def test_v1_error_distribution(client):
    r = client.get("/api/v1/metrics/error-distribution?start=2026-01-01&end=2026-01-31")
    assert r.status_code == 200
    data = r.json()
    assert "bins" in data
    assert len(data["bins"]) == 7
    assert data["total_count"] == 744


def test_v1_time_of_day(client):
    r = client.get("/api/v1/metrics/time-of-day?start=2026-01-01&end=2026-01-31")
    assert r.status_code == 200
    data = r.json()
    assert "groups" in data
    assert len(data["groups"]) == 8


def test_v1_forecast_history(client):
    r = client.get("/api/v1/forecast-history?start=2026-01-01&end=2026-01-31")
    assert r.status_code == 200
    data = r.json()
    assert data["retention"] == "full"
    assert "publications" in data


def test_v1_data_quality(client):
    r = client.get("/api/v1/data-quality?start=2026-01-01&end=2026-01-31")
    assert r.status_code == 200
    data = r.json()
    assert data["expected_intervals"] == 1488
    assert data["valid_matched_intervals"] == 744
    assert len(data["exclusion_reasons"]) > 0
