# Wind Forecast Evaluation & Analytics Platform

An end-to-end platform for evaluating wind generation forecasts against actual Elexon outturns.

- **Data / Outputs (`output/`)**: Standardized Elexon WINDFOR and FUELHH dataset for January 2026 (1,488 half-hourly settlement intervals, 744 decision-eligible forecasts).
- **Backend (`backend/`)**: FastAPI statistical calculation engine (Module 2) calculating MAE, RMSE, MBE, daily aggregations, time-of-day profiles, error distributions, and audit trails. Serves both `/api/v1` (dashboard) and `/api/analytics` (module contract).
- **Frontend (`frontend/`)**: React 19 + TypeScript + Vite decision-support dashboard (Module 3) rendering headline KPIs, error distribution charts, time-of-day breakdowns, interval monitor, and data quality metrics.

---

## Repository Structure

```
wind_forecast_main/
├── backend/
│   ├── api/
│   │   ├── routes.py            # /api/analytics endpoints
│   │   ├── v1_routes.py         # /api/v1 dashboard endpoints
│   │   └── schemas.py           # Pydantic schemas
│   ├── aggregations.py          # Daily & time-of-day groupings
│   ├── config.py                # AnalyticsConfig & constants
│   ├── contract.py              # Data contract & schema definitions
│   ├── data_quality.py          # Validation & cutoff eligibility
│   ├── forecast_comparison.py   # Forecast revision comparison
│   ├── main.py                  # FastAPI app factory with CORS & health
│   ├── metrics.py               # Pure error, MAE, RMSE, MBE calculations
│   ├── providers.py             # FileDatasetProvider (reads output/ directory)
│   ├── service.py               # AnalyticsService orchestration
│   └── Dockerfile               # Backend container configuration
├── frontend/
│   ├── src/
│   │   ├── components/          # Charts, tables, banners, KPI cards
│   │   ├── context/             # FilterContext (Jan 2026 default), StatusContext
│   │   ├── hooks/               # useAnalytics query hook
│   │   ├── pages/               # Overview, AccuracyAnalytics, ForecastMonitor, ForecastHistory
│   │   ├── services/            # analyticsApi.ts, contract.ts, adapters.ts
│   │   └── utils/               # Display formatting & date helpers
│   ├── .env                     # Points VITE_API_BASE_URL to http://localhost:8000
│   ├── package.json             # React 19, Vite, Recharts
│   └── vite.config.ts           # Vite dev server on port 5173
├── output/
│   ├── matched_dataset.csv      # Standardized matched intervals
│   ├── valid_pairs.csv          # Filtered valid evaluation pairs
│   ├── quarantine.csv           # Flagged records
│   ├── expected_intervals.csv   # Expected interval schedule
│   ├── forecasts.csv            # Unflagged forecast rows
│   ├── actuals.csv              # Actual generation rows
│   ├── meta.json                # Dataset metadata
│   └── data_quality_report.json # Upstream data quality summary
├── tests/                       # 100 passing unit, integration & API tests
├── docker-compose.yml           # Runs backend (8000) & frontend (8080)
├── pytest.ini                   # Pytest configuration
└── requirements.txt             # Python dependencies
```

---

## Quickstart

### 1. Backend Setup & Run

```bash
# Install Python dependencies (Python 3.10+)
pip install -r requirements.txt

# Start the FastAPI analytics service on port 8000
uvicorn backend.main:app --reload --port 8000
```
- Health check: `http://localhost:8000/health`
- Interactive Swagger docs: `http://localhost:8000/docs`

### 2. Frontend Setup & Run

```bash
cd frontend

# Install Node dependencies (Node 20+)
npm install

# Start Vite dev server on port 5173
npm run dev
```
- Open `http://localhost:5173` in your browser.
- The dashboard automatically connects to `http://localhost:8000` and displays January 2026 data.

---

## Running with Docker Compose

```bash
docker compose up --build
```
- Dashboard: `http://localhost:8080`
- API / Health: `http://localhost:8000/health`

---

## Running Tests

### Python Backend & API Tests (100 tests)
```bash
pytest
```

### Frontend TypeScript Verification & Production Build
```bash
cd frontend
npm run typecheck
npm run build
```
