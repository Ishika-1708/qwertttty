/**
 * Typed models of the Module 2 (FastAPI) responses, as the dashboard consumes them.
 *
 * ⚠️  CONTRACT STATUS: ASSUMED.
 * The Module 2 contract was not available when this module was written. Every
 * field below is an ASSUMPTION, listed in the README under "Contract assumptions
 * and open questions". The only code that knows the wire format is
 * `services/contract.ts` (paths and query params) and `services/adapters.ts`
 * (field-by-field normalisation). If Module 2 differs, change those two files;
 * these types, the hooks and the UI should not need to change.
 *
 * INTEGRITY RULE: every number here was calculated by the backend. The frontend
 * never derives MAE, RMSE, MBE, error, coverage or counts. `null` means
 * "unavailable" and must be rendered as unavailable - never as zero.
 */

export type Metric = "mae" | "rmse" | "mbe";

/** ISO-8601 timestamp string with offset, e.g. "2026-03-29T00:30:00Z". */
export type IsoTimestamp = string;
/** Local settlement date, "YYYY-MM-DD" (Europe/London). */
export type IsoDate = string;

export interface DateRange {
  start: IsoDate;
  end: IsoDate;
}

/** How the purchasing decision cutoff is described by the backend (display only). */
export interface CutoffInfo {
  /** Human-readable rule, e.g. "09:00 London time on the day before delivery". */
  description: string | null;
  /** Optional machine value if the backend provides one. Display only. */
  hours_before_delivery: number | null;
}

export type Completeness = "complete" | "incomplete" | "unknown";

/* ------------------------------ /health ------------------------------ */

export interface HealthResponse {
  status: "ok" | "degraded" | "down" | string;
  version: string | null;
  checked_at: IsoTimestamp | null;
  /** Last time Module 1/2 successfully ingested data, if exposed. */
  last_successful_ingest_at: IsoTimestamp | null;
}

/* ------------------------------ summary ------------------------------ */

export interface SummaryMetrics {
  mae: number | null;
  rmse: number | null;
  mbe: number | null;
}

export interface SummaryResponse {
  period: DateRange;
  decision_cutoff: CutoffInfo;
  unit: "MW";
  metrics: SummaryMetrics;
  /** Intervals with both an eligible forecast and an actual that were scored. */
  valid_matched_intervals: number | null;
  /** Intervals expected in the period (varies with DST). */
  expected_intervals: number | null;
  /** Backend-calculated coverage, 0-100. Displayed as returned. */
  coverage_pct: number | null;
  /** Backend flag. When absent the adapter reports "unknown", not "complete". */
  completeness: Completeness;
  /** Backend-supplied warnings, shown verbatim. */
  warnings: string[];
  /** Timestamp the backend says its data is current to. */
  data_as_of: IsoTimestamp | null;
}

/* ------------------------------ intervals ------------------------------ */

export type IntervalStatus =
  | "matched"
  | "missing_actual"
  | "missing_forecast"
  | "unmatched"
  | "excluded"
  | "invalid"
  | "unknown";

export interface IntervalRecord {
  /** Start of the delivery (settlement) interval. */
  delivery_time: IsoTimestamp;
  forecast_mw: number | null;
  actual_mw: number | null;
  /** Signed error = forecast - actual, calculated by the backend. */
  error_mw: number | null;
  forecast_published_at: IsoTimestamp | null;
  decision_cutoff_at: IsoTimestamp | null;
  /** Was this forecast published at or before the decision cutoff? */
  available_by_cutoff: boolean | null;
  status: IntervalStatus;
  exclusion_reason: string | null;
}

export interface IntervalsResponse {
  period: DateRange;
  intervals: IntervalRecord[];
  /** Number of records the backend says exist for the period. */
  total_count: number | null;
}

/* ------------------------------ aggregates ------------------------------ */

export interface DailyMetricPoint {
  date: IsoDate;
  mae: number | null;
  rmse: number | null;
  mbe: number | null;
  sample_count: number;
  expected_intervals: number | null;
  coverage_pct: number | null;
}

export interface DailyMetricsResponse {
  period: DateRange;
  points: DailyMetricPoint[];
  /** Metrics the backend actually returns values for. Drives the metric switch. */
  available_metrics: Metric[];
}

export interface ErrorDistributionBin {
  /** Inclusive lower edge of |error| in MW. */
  lower_mw: number;
  /** Exclusive upper edge in MW; null = open-ended top bin. */
  upper_mw: number | null;
  count: number;
}

export interface ErrorDistributionResponse {
  period: DateRange;
  unit: "MW";
  bins: ErrorDistributionBin[];
  total_count: number | null;
}

export interface TimeOfDayGroup {
  /** Label from the backend, e.g. "00:00-03:00". */
  label: string;
  mae: number | null;
  rmse: number | null;
  mbe: number | null;
  sample_count: number;
}

export interface TimeOfDayResponse {
  period: DateRange;
  grouping: string | null;
  groups: TimeOfDayGroup[];
  available_metrics: Metric[];
}

/* ------------------------------ history + quality ------------------------------ */

export type HistoryRetention = "full" | "partial" | "none" | "unknown";

export interface ForecastPublication {
  published_at: IsoTimestamp;
  version_id: string | null;
  intervals_covered: number | null;
  /** Backend says this publication is the one used for the evaluation. */
  selected: boolean;
}

export interface ForecastHistoryResponse {
  period: DateRange;
  decision_cutoff: CutoffInfo;
  retention: HistoryRetention;
  retention_note: string | null;
  selected_version_description: string | null;
  publications: ForecastPublication[];
}

export interface ExclusionReasonCount {
  reason: string;
  count: number;
}

export interface DataQualityResponse {
  period: DateRange;
  expected_intervals: number | null;
  valid_matched_intervals: number | null;
  missing_actuals: number | null;
  missing_forecasts: number | null;
  unmatched_intervals: number | null;
  excluded_or_invalid: number | null;
  exclusion_reasons: ExclusionReasonCount[];
  coverage_pct: number | null;
  last_successful_update_at: IsoTimestamp | null;
}
