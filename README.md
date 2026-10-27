# Wind Forecast Evaluation & Analytics Platform

An end-to-end platform that evaluates the accuracy of **wind generation forecasts already published by Elexon**
(WINDFOR) against **actual wind generation** (FUELHH) for Great Britain. It does not train any forecasting model:
it answers *"how good were the forecasts that were actually available at the time of the purchasing decision?"*

> Evaluation window: January 2026 decisions (delivery 2 Jan – 1 Feb 2026). Data source: Elexon BMRS Insights API.

---

## Table of contents
1. [Architecture](#architecture)
2. [Repository layout](#repository-layout)
3. [Key design principles](#key-design-principles)
4. [Quick start](#quick-start)
5. [Module 1 – Data acquisition & processing](#module-1--data-acquisition--processing)
6. [Module 2 – Backend: analytics & API](#module-2--backend-analytics--api)
7. [Module 3 – Frontend dashboard](#module-3--frontend-dashboard)
8. [Data contract between modules](#data-contract-between-modules)
9. [Testing](#testing)
10. [Configuration](#configuration)
11. [Assumptions and known limitations](#assumptions-and-known-limitations)
12. [Deployment](#deployment)
13. [AI assistance](#ai-assistance)

---

## Architecture

```
 Elexon BMRS API                                                    Browser
 (FUELHH, WINDFOR)                                                     ▲
        │                                                              │ HTTP/JSON
        ▼                                                              │
 ┌──────────────┐   CSV / JSON    ┌───────────────────────┐   ┌──────────────────┐
 │   Module 1   │ ───────────────►│       Module 2        │──►│     Frontend     │
 │ fetch, clean │   output/       │ metrics, aggregation, │   │  React + Vite    │
 │ validate,    │   (the contract)│ data quality, REST API│   │  dashboard       │
 │ select, match│                 └───────────────────────┘   └──────────────────┘
 └──────────────┘
   batch job                          read-only consumer
```

* **Module 1** (data acquisition) is a batch job: run it to (re)produce the dataset.
* **Module 2** (the backend) never calls Elexon; it only reads Module 1's output, so analytics are reproducible and testable offline.
* **Module 3** (the frontend) only displays what the API returns and does not recompute metrics.

## Repository layout

```
wind-forecast-platform/
├── frontend/     Module 3: React + TypeScript + Vite dashboard
├── backend/      Module 2 (entire backend): metrics, aggregations, data-quality, REST API, tests
├── module1/      Module 1: Elexon fetch, cleaning, validation, forecast selection, matching
├── output/       Module 1 output = the hand-off to Module 2 (CSV/JSON)
└── README.md
```

## Key design principles

1. **No invented data.** A missing or invalid value is `null`/unavailable, never `0` and never an estimate.
   API failures raise explicit errors or use clearly labelled cached data.
2. **No look-ahead bias.** For each delivery interval, only the latest forecast with `publish_time <= decision_cutoff`
   is used. A forecast published after the cutoff is never selected.
3. **Match on delivery interval**, never on publish time.
4. **Decision window and delivery window are separate and configurable.** A decision made on 31 January may concern
   1 February delivery. Several decision rules (different cutoffs) can be defined.
5. **Quality is reported, not hidden.** Missing, invalid, duplicate and unmatched records are quarantined with a
   reason and summarised in a data-quality report. Only valid matched pairs feed accuracy metrics.
6. **Separation of concerns.** Acquisition, analytics and presentation are independent and independently tested.

## Quick start

**Prerequisites:** Python 3.11+, Node.js 18+, npm.

```bash
# 1. Module 1: produce the dataset (needs internet for the first run)
cd module1
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py --out-dir ../output --cache-dir ../.cache/elexon

# 2. Module 2: start the API
cd ../backend
pip install -r requirements.txt
uvicorn [module2.api.<app_module>:app] --reload --port 8000     # [CONFIRM app path]

# 3. Frontend
cd ../frontend
cp .env.example .env          # set the API base URL, e.g. http://localhost:8000
npm install
npm run dev                   # http://localhost:5173
```

Useful Module 1 flags: `--no-cache` (ignore cached responses), `--offline` (cache only),
`--allow-stale-cache` (use cached data if the API fails; it is labelled as such in the report), `-v` (verbose).
`[CONFIRM against python main.py -h]`

## Module 1 – Data acquisition & processing

Pipeline: **fetch → filter → normalise → validate → select eligible forecast → match → export.**

| Step | What it does |
|---|---|
| Fetch | Calls the FUELHH and WINDFOR stream endpoints with time-range parameters, retries transient failures, caches responses, raises explicit errors on timeouts / HTTP errors / bad bodies. |
| Filter | Keeps `fuelType == "WIND"` for actuals; restricts both datasets to the configured windows. |
| Normalise | Timezone-aware UTC timestamps, numeric MW values, internal schema (`delivery_time`, `generation_mw`, `publish_time`, `record_type`). |
| Validate | Detects missing values, duplicates (documented keep rule), invalid values, delivery-interval gaps and invalid timestamps (quarantined with a reason). Distinguishes a *missing record* from a *present but invalid value*. |
| Select | For each interval, the latest forecast published at or before the decision cutoff, or "unavailable". |
| Match | Joins forecast and actual on `delivery_time` with Pandas. Only valid pairs are passed on for accuracy metrics. |
| Export | `matched_dataset.csv/json`, `valid_pairs.csv`, `quarantine.csv`, data-quality report. |

## Module 2 – Backend: analytics & API

Module 2 evaluates how accurate the published wind forecasts were at the time purchasing decisions were made. For each delivery interval it takes the latest forecast published by the decision cutoff, matches it to the actual generation, and computes signed and absolute errors, plus MAE, RMSE and bias (MBE), all in MW. It then breaks these results down by delivery date and time of day, compares forecast versions by publication lead time, and reports data-quality and coverage statistics (expected vs valid intervals, exclusions by reason). Everything is served to the dashboard through five FastAPI endpoints under /api/analytics.

Files: `metrics.py`, `aggregations.py`, `forecast_comparison.py`, `data_quality.py`, `contract.py`, `providers.py`,
`service.py`, `api/`. Module 2 validates the Module 1 contract on load and computes metrics only from valid pairs.

## Module 3 – Frontend dashboard

React + TypeScript (Vite). Pages: **Overview**, **Accuracy Analytics**, **Forecast History**, **Forecast Monitor**.
Shared components cover metric cards, forecast-vs-actual and error-trend charts, an aggregate table, an interval
detail view, completeness / data-quality banners and a system-status panel. Metrics come from the API; the frontend does not
recompute them (see `test_dashboard_no_recompute.py`).

## Data contract between modules

Proposed Module 1 → Module 2 schema (`matched_dataset`, `valid_pairs`):

| Field | Meaning |
|---|---|
| `delivery_time` | Start of the delivery interval (UTC) |
| `decision_cutoff` | Last instant at which information was usable (UTC) |
| `forecast_publish_time` | Publish time of the selected forecast (always ≤ cutoff) |
| `forecast_generation_mw` | Forecast, MW (null if unavailable) |
| `actual_generation_mw` | Actual, MW (null if unavailable) |
| `forecast_available`, `actual_available` | Booleans |
| `quality_status` | Row status; only fully valid rows are used for accuracy metrics |

## Testing

```bash
cd backend && pytest                                     # Module 2
cd module1 && python -m unittest discover -s tests -t .  # Module 1 (or pytest)
cd frontend && npm run build                             # type-check + build
```
Module 1 tests use mocked API responses and cover API failure/timeout, empty responses, duplicates, invalid values and
timestamps, missing forecasts/actuals, interval gaps, forecasts published just before/after the cutoff, and multiple cutoffs.

## Configuration

| Setting | Where | Notes |
|---|---|---|
| Decision window, delivery window, decision rules | Module 1 config | Cutoff schedule is an assumption; see below |
| Output directory | `--out-dir` | Shared with Module 2 |
| API base URL | `frontend/.env` | `VITE_API_BASE_URL` `[CONFIRM name]` |
| CORS origins | backend | Must allow the frontend origin |

## Assumptions and known limitations

* The brief did not define a cutoff schedule; the default is a day-ahead decision at `[09:00 UTC on D-1 – CONFIRM]`.
* WINDFOR is reported to be hourly and FUELHH half-hourly. Evaluation interval handling must match
  (`[CONFIRM how your Module 1 aligns them]`). Verify against a live response.
* Generation is treated as MW; values outside a plausible range are quarantined, not clipped.
* FUELHH values can be revised; re-run with the cache bypassed for final figures.
* Results cover a single month and one set of decision rules; they are not a general statement about the forecast provider.

## Deployment
The frontend is deployed on Vercel as a separate project, while the FastAPI backend is hosted independently at https://backend-qwert.vercel.app. The frontend communicates with the backend through REST API endpoints, configured using the VITE_API_BASE_URL environment variable. The backend exposes endpoints for health checks, metrics, intervals, and forecast history. CORS is configured to allow requests from the frontend's production domain.

## AI assistance

The system design and architecture of this platform are my own work. Because of a tight project deadline, I used an
AI coding assistant to accelerate implementation by generating boilerplate code, which I then reviewed, adapted and
debugged myself.

**What I designed and decided**
* The overall three-module architecture: **Module 1** (data acquisition and processing), **Module 2** (the entire
  backend: analytics and API) and **Module 3** (the frontend dashboard), and the data contract between them.
* The evaluation methodology: the no-look-ahead forecast selection rule, separate decision and delivery windows,
  configurable decision cutoffs, matching on delivery interval, and the "missing is never zero" data-handling policy.
* The data-quality approach (quarantine with reasons, valid-pairs-only metrics) and the structure of the backend
  and the dashboard.

**Where AI assistance was used**
* **Module 1:** initial boilerplate for the fetcher, processor, forecast selector and unit tests.
* **Module 2:** boilerplate for the backend structure (metrics, aggregations, data-quality, service layer, API and tests).
* **Module 3:** boilerplate for the frontend components, pages, hooks and API service layer.

**What I did with it**
* Adapted the generated code to my architecture, data contract and project requirements.
* Ran the pipeline end to end, and debugged and fixed the issues that came up, including integration between the
  modules.
* Verified outputs against the data and the documented assumptions.

AI-generated code was treated as a starting draft, not a finished product.
