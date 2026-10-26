/**
 * ============================================================================
 *  MODULE 2 CONTRACT ADAPTER  -  *** ALL OF THIS IS ASSUMED ***
 * ============================================================================
 * Module 2's endpoint paths and query parameters were not documented when this
 * dashboard was built. Nothing here has been confirmed. This file is the ONLY
 * place that knows them, so aligning with the real API means editing this file
 * (and `adapters.ts` for response field names) and nothing else.
 *
 * `optional: true` marks endpoints the spec says are "where the API supports
 * it". A 404/501 from an optional endpoint is shown as "not provided by the
 * backend" instead of as a failure.
 *
 * OPEN QUESTIONS (also in README):
 *  1. Are these paths and the /api/v1 prefix correct?
 *  2. Does Module 2 accept a cutoff parameter? We send none and only DISPLAY the
 *     cutoff the backend reports.
 *  3. Does /intervals return the whole range at once, or paginate?
 *  4. Is coverage_pct 0-100 (assumed) or a 0-1 ratio?
 *  5. Which of time-of-day, error-distribution, forecast-history and data-quality
 *     exist?
 * ============================================================================
 */

export interface EndpointDef {
  path: string;
  /** Optional endpoints degrade to a "not provided" state on 404/501. */
  optional: boolean;
}

export const ENDPOINTS = {
  // Health check - the spec requires one. Path is assumed.
  health: { path: "/health", optional: false },
  // Headline KPIs + coverage for a period.
  summary: { path: "/api/v1/metrics/summary", optional: false },
  // Interval-level forecast, actual, error, publication time, eligibility.
  intervals: { path: "/api/v1/intervals", optional: false },
  // One row per delivery date with backend-calculated MAE/RMSE/MBE + sample count.
  dailyMetrics: { path: "/api/v1/metrics/daily", optional: false },
  // Binned |error| counts.
  errorDistribution: { path: "/api/v1/metrics/error-distribution", optional: true },
  // Metrics grouped by time of day (only if Module 2 exposes it).
  timeOfDay: { path: "/api/v1/metrics/time-of-day", optional: true },
  // Publication history (only where Module 1 retains it).
  forecastHistory: { path: "/api/v1/forecast-history", optional: true },
  // Missing / unmatched / excluded counts.
  dataQuality: { path: "/api/v1/data-quality", optional: true },
} as const satisfies Record<string, EndpointDef>;

export type EndpointKey = keyof typeof ENDPOINTS;

/**
 * Query parameter names. Dates are local settlement dates (YYYY-MM-DD), inclusive.
 * ASSUMPTION: Module 2 accepts `start` and `end`.
 */
export const PARAM_NAMES = {
  start: "start",
  end: "end",
} as const;

/** Client-side request timeout. */
export const REQUEST_TIMEOUT_MS = 20_000;
