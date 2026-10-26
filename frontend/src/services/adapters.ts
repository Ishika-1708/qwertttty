/**
 * Response adapters: unknown JSON -> typed models.
 *
 * ASSUMPTION: field names below are the assumed Module 2 contract (see
 * contract.ts). Each adapter validates shape and throws `AdapterError` when the
 * body cannot be trusted; the API layer turns that into an `invalid_response`.
 *
 * These functions only RENAME, VALIDATE and DEFAULT-TO-NULL. They never compute
 * a metric, a count, an error or a coverage figure.
 */
import type {
  Completeness,
  CutoffInfo,
  DailyMetricPoint,
  DailyMetricsResponse,
  DataQualityResponse,
  DateRange,
  ErrorDistributionResponse,
  ForecastHistoryResponse,
  ForecastPublication,
  HealthResponse,
  HistoryRetention,
  IntervalRecord,
  IntervalStatus,
  IntervalsResponse,
  Metric,
  SummaryResponse,
  TimeOfDayGroup,
  TimeOfDayResponse,
} from "../types";

export class AdapterError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AdapterError";
  }
}

type Obj = Record<string, unknown>;

/* ------------------------------ readers ------------------------------ */

function asObj(v: unknown, where: string): Obj {
  if (typeof v !== "object" || v === null || Array.isArray(v)) {
    throw new AdapterError(`Expected an object at ${where}`);
  }
  return v as Obj;
}

function asArr(v: unknown, where: string): unknown[] {
  if (!Array.isArray(v)) throw new AdapterError(`Expected an array at ${where}`);
  return v;
}

/** Number or null. NaN, strings and missing values become null ("unavailable"), never 0. */
function numOrNull(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function strOrNull(v: unknown): string | null {
  return typeof v === "string" && v.length > 0 ? v : null;
}

function reqStr(o: Obj, key: string, where: string): string {
  const v = o[key];
  if (typeof v !== "string" || v.length === 0) throw new AdapterError(`Missing string "${key}" at ${where}`);
  return v;
}

function boolOrNull(v: unknown): boolean | null {
  return typeof v === "boolean" ? v : null;
}

function strArray(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : [];
}

function readPeriod(o: Obj, where: string): DateRange {
  const p = asObj(o["period"], `${where}.period`);
  return { start: reqStr(p, "start", `${where}.period`), end: reqStr(p, "end", `${where}.period`) };
}

function readCutoff(v: unknown): CutoffInfo {
  if (typeof v !== "object" || v === null) return { description: null, hours_before_delivery: null };
  const o = v as Obj;
  return {
    description: strOrNull(o["description"]),
    hours_before_delivery: numOrNull(o["hours_before_delivery"]),
  };
}

const METRICS: readonly Metric[] = ["mae", "rmse", "mbe"];

function readMetricList(v: unknown): Metric[] {
  return Array.isArray(v) ? v.filter((m): m is Metric => METRICS.includes(m as Metric)) : [];
}

/** Which metrics have at least one non-null value in the rows (used only when the backend omits `available_metrics`). */
function metricsPresent(rows: Array<Record<Metric, number | null>>): Metric[] {
  return METRICS.filter((m) => rows.some((r) => r[m] !== null));
}

/* ------------------------------ adapters ------------------------------ */

export function adaptHealth(raw: unknown): HealthResponse {
  const o = asObj(raw, "health");
  return {
    status: typeof o["status"] === "string" ? o["status"] : "unknown",
    version: strOrNull(o["version"]),
    checked_at: strOrNull(o["checked_at"]),
    last_successful_ingest_at: strOrNull(o["last_successful_ingest_at"]),
  };
}

export function adaptSummary(raw: unknown): SummaryResponse {
  const o = asObj(raw, "summary");
  const m = asObj(o["metrics"], "summary.metrics");
  const rawCompleteness = o["completeness"];
  const completeness: Completeness =
    rawCompleteness === "complete" || rawCompleteness === "incomplete" ? rawCompleteness : "unknown";
  return {
    period: readPeriod(o, "summary"),
    decision_cutoff: readCutoff(o["decision_cutoff"]),
    unit: "MW",
    metrics: { mae: numOrNull(m["mae"]), rmse: numOrNull(m["rmse"]), mbe: numOrNull(m["mbe"]) },
    valid_matched_intervals: numOrNull(o["valid_matched_intervals"]),
    expected_intervals: numOrNull(o["expected_intervals"]),
    coverage_pct: numOrNull(o["coverage_pct"]),
    completeness,
    warnings: strArray(o["warnings"]),
    data_as_of: strOrNull(o["data_as_of"]),
  };
}

const INTERVAL_STATUSES: readonly IntervalStatus[] = [
  "matched",
  "missing_actual",
  "missing_forecast",
  "unmatched",
  "excluded",
  "invalid",
];

function adaptInterval(raw: unknown, i: number): IntervalRecord {
  const o = asObj(raw, `intervals[${i}]`);
  const status = o["status"];
  return {
    delivery_time: reqStr(o, "delivery_time", `intervals[${i}]`),
    forecast_mw: numOrNull(o["forecast_mw"]),
    actual_mw: numOrNull(o["actual_mw"]),
    error_mw: numOrNull(o["error_mw"]),
    forecast_published_at: strOrNull(o["forecast_published_at"]),
    decision_cutoff_at: strOrNull(o["decision_cutoff_at"]),
    available_by_cutoff: boolOrNull(o["available_by_cutoff"]),
    status: INTERVAL_STATUSES.includes(status as IntervalStatus) ? (status as IntervalStatus) : "unknown",
    exclusion_reason: strOrNull(o["exclusion_reason"]),
  };
}

export function adaptIntervals(raw: unknown): IntervalsResponse {
  const o = asObj(raw, "intervals");
  return {
    period: readPeriod(o, "intervals"),
    intervals: asArr(o["intervals"], "intervals.intervals").map(adaptInterval),
    total_count: numOrNull(o["total_count"]),
  };
}

function adaptDailyPoint(raw: unknown, i: number): DailyMetricPoint {
  const o = asObj(raw, `points[${i}]`);
  const sample = numOrNull(o["sample_count"]);
  if (sample === null) throw new AdapterError(`Missing sample_count at points[${i}]`);
  return {
    date: reqStr(o, "date", `points[${i}]`),
    mae: numOrNull(o["mae"]),
    rmse: numOrNull(o["rmse"]),
    mbe: numOrNull(o["mbe"]),
    sample_count: sample,
    expected_intervals: numOrNull(o["expected_intervals"]),
    coverage_pct: numOrNull(o["coverage_pct"]),
  };
}

export function adaptDailyMetrics(raw: unknown): DailyMetricsResponse {
  const o = asObj(raw, "daily");
  const points = asArr(o["points"], "daily.points").map(adaptDailyPoint);
  const declared = readMetricList(o["available_metrics"]);
  return {
    period: readPeriod(o, "daily"),
    points,
    available_metrics: declared.length > 0 ? declared : metricsPresent(points),
  };
}

export function adaptErrorDistribution(raw: unknown): ErrorDistributionResponse {
  const o = asObj(raw, "distribution");
  return {
    period: readPeriod(o, "distribution"),
    unit: "MW",
    total_count: numOrNull(o["total_count"]),
    bins: asArr(o["bins"], "distribution.bins").map((b, i) => {
      const bo = asObj(b, `bins[${i}]`);
      const lower = numOrNull(bo["lower_mw"]);
      const count = numOrNull(bo["count"]);
      if (lower === null || count === null) throw new AdapterError(`Invalid bin at bins[${i}]`);
      return { lower_mw: lower, upper_mw: numOrNull(bo["upper_mw"]), count };
    }),
  };
}

function adaptTimeOfDayGroup(raw: unknown, i: number): TimeOfDayGroup {
  const o = asObj(raw, `groups[${i}]`);
  const sample = numOrNull(o["sample_count"]);
  if (sample === null) throw new AdapterError(`Missing sample_count at groups[${i}]`);
  return {
    label: reqStr(o, "label", `groups[${i}]`),
    mae: numOrNull(o["mae"]),
    rmse: numOrNull(o["rmse"]),
    mbe: numOrNull(o["mbe"]),
    sample_count: sample,
  };
}

export function adaptTimeOfDay(raw: unknown): TimeOfDayResponse {
  const o = asObj(raw, "time-of-day");
  const groups = asArr(o["groups"], "time-of-day.groups").map(adaptTimeOfDayGroup);
  const declared = readMetricList(o["available_metrics"]);
  return {
    period: readPeriod(o, "time-of-day"),
    grouping: strOrNull(o["grouping"]),
    groups,
    available_metrics: declared.length > 0 ? declared : metricsPresent(groups),
  };
}

function adaptPublication(raw: unknown, i: number): ForecastPublication {
  const o = asObj(raw, `publications[${i}]`);
  return {
    published_at: reqStr(o, "published_at", `publications[${i}]`),
    version_id: strOrNull(o["version_id"]),
    intervals_covered: numOrNull(o["intervals_covered"]),
    selected: o["selected"] === true,
  };
}

export function adaptForecastHistory(raw: unknown): ForecastHistoryResponse {
  const o = asObj(raw, "forecast-history");
  const r = o["retention"];
  const retention: HistoryRetention = r === "full" || r === "partial" || r === "none" ? r : "unknown";
  return {
    period: readPeriod(o, "forecast-history"),
    decision_cutoff: readCutoff(o["decision_cutoff"]),
    retention,
    retention_note: strOrNull(o["retention_note"]),
    selected_version_description: strOrNull(o["selected_version_description"]),
    publications: asArr(o["publications"] ?? [], "forecast-history.publications").map(adaptPublication),
  };
}

export function adaptDataQuality(raw: unknown): DataQualityResponse {
  const o = asObj(raw, "data-quality");
  const reasons = Array.isArray(o["exclusion_reasons"]) ? o["exclusion_reasons"] : [];
  return {
    period: readPeriod(o, "data-quality"),
    expected_intervals: numOrNull(o["expected_intervals"]),
    valid_matched_intervals: numOrNull(o["valid_matched_intervals"]),
    missing_actuals: numOrNull(o["missing_actuals"]),
    missing_forecasts: numOrNull(o["missing_forecasts"]),
    unmatched_intervals: numOrNull(o["unmatched_intervals"]),
    excluded_or_invalid: numOrNull(o["excluded_or_invalid"]),
    exclusion_reasons: reasons.flatMap((x) => {
      if (typeof x !== "object" || x === null) return [];
      const ro = x as Obj;
      const reason = strOrNull(ro["reason"]);
      const count = numOrNull(ro["count"]);
      return reason !== null && count !== null ? [{ reason, count }] : [];
    }),
    coverage_pct: numOrNull(o["coverage_pct"]),
    last_successful_update_at: strOrNull(o["last_successful_update_at"]),
  };
}
