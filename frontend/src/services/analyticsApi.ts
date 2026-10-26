/**
 * Typed client for the Module 2 analytics API.
 *
 * - Base URL comes from `import.meta.env.VITE_API_BASE_URL`. There is no
 *   hardcoded fallback; a missing value surfaces as a "config" error in the UI.
 * - Every failure is an `ApiError` with a `kind`, so views render consistently.
 * - Paths / params live in `contract.ts`; field mapping lives in `adapters.ts`.
 * - Nothing here calculates a metric. Responses are passed through as returned.
 */
import type {
  DailyMetricsResponse,
  DataQualityResponse,
  DateRange,
  ErrorDistributionResponse,
  ForecastHistoryResponse,
  HealthResponse,
  IntervalsResponse,
  SummaryResponse,
  TimeOfDayResponse,
} from "../types";
import {
  adaptDailyMetrics,
  adaptDataQuality,
  adaptErrorDistribution,
  adaptForecastHistory,
  adaptHealth,
  adaptIntervals,
  adaptSummary,
  adaptTimeOfDay,
  AdapterError,
} from "./adapters";
import { ApiError } from "./apiError";
import { ENDPOINTS, PARAM_NAMES, REQUEST_TIMEOUT_MS, type EndpointKey } from "./contract";

/* ------------------------------ configuration ------------------------------ */

/** Resolved lazily so a missing variable is reported through the UI, not as a crash at import time. */
export function getApiBaseUrl(): string {
  const raw = import.meta.env.VITE_API_BASE_URL?.trim();
  if (!raw) {
    throw new ApiError(
      "config",
      "VITE_API_BASE_URL is not set. Set it to the public URL of the analytics backend and rebuild.",
      "config",
    );
  }
  if (!/^https?:\/\//i.test(raw)) {
    throw new ApiError("config", `VITE_API_BASE_URL must start with http:// or https:// (got "${raw}").`, "config");
  }
  return raw.replace(/\/+$/, "");
}

/** For display in the status panel only. Returns null when unconfigured. */
export function describeApiBaseUrl(): string | null {
  try {
    return getApiBaseUrl();
  } catch {
    return null;
  }
}

/* ------------------------------ transport ------------------------------ */

type Query = Record<string, string | number | undefined>;

function buildUrl(base: string, path: string, query: Query): string {
  const url = new URL(base + path);
  for (const [k, v] of Object.entries(query)) {
    if (v !== undefined) url.searchParams.set(k, String(v));
  }
  return url.toString();
}

/** FastAPI errors look like { detail: "msg" } or { detail: [{ msg, loc }] }. */
function extractDetail(body: unknown): string | null {
  if (typeof body !== "object" || body === null) return null;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d) => (typeof d === "object" && d !== null ? (d as { msg?: unknown }).msg : null))
      .filter((m): m is string => typeof m === "string");
    return msgs.length > 0 ? msgs.join("; ") : null;
  }
  return null;
}

async function request<T>(
  key: EndpointKey,
  query: Query,
  adapt: (raw: unknown) => T,
  signal?: AbortSignal,
): Promise<T> {
  const def = ENDPOINTS[key];
  const endpoint = def.path;
  const base = getApiBaseUrl();

  // Combine the caller's abort signal with a timeout, remembering which one fired.
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, REQUEST_TIMEOUT_MS);
  const onCallerAbort = () => controller.abort();
  signal?.addEventListener("abort", onCallerAbort);

  try {
    let response: Response;
    try {
      response = await fetch(buildUrl(base, endpoint, query), {
        headers: { Accept: "application/json" },
        signal: controller.signal,
      });
    } catch (e) {
      if (timedOut) throw new ApiError("timeout", `No response from ${endpoint} within ${REQUEST_TIMEOUT_MS / 1000}s.`, endpoint);
      if (e instanceof DOMException && e.name === "AbortError") throw e; // caller cancelled; not an error to show
      throw new ApiError(
        "network",
        "The request did not reach the backend. Check that it is running, that this browser is online, and that CORS allows this site.",
        endpoint,
      );
    }

    let body: unknown = null;
    const text = await response.text();
    if (text.length > 0) {
      try {
        body = JSON.parse(text);
      } catch {
        if (response.ok) throw new ApiError("invalid_response", "The backend returned a response that is not valid JSON.", endpoint, response.status);
      }
    }

    if (!response.ok) {
      if (response.status === 501 || (response.status === 404 && def.optional)) {
        throw new ApiError("not_supported", "The analytics backend does not expose this view.", endpoint, response.status);
      }
      const detail = extractDetail(body);
      throw new ApiError("http", detail ?? response.statusText ?? "Request failed.", endpoint, response.status);
    }

    try {
      return adapt(body);
    } catch (e) {
      if (e instanceof AdapterError) throw new ApiError("invalid_response", e.message, endpoint, response.status);
      throw e;
    }
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onCallerAbort);
  }
}

function rangeQuery(range: DateRange): Query {
  return { [PARAM_NAMES.start]: range.start, [PARAM_NAMES.end]: range.end };
}

/* ------------------------------ public API ------------------------------ */

export const analyticsApi = {
  getHealth: (signal?: AbortSignal): Promise<HealthResponse> => request("health", {}, adaptHealth, signal),

  getSummary: (range: DateRange, signal?: AbortSignal): Promise<SummaryResponse> =>
    request("summary", rangeQuery(range), adaptSummary, signal),

  getIntervals: (range: DateRange, signal?: AbortSignal): Promise<IntervalsResponse> =>
    request("intervals", rangeQuery(range), adaptIntervals, signal),

  getDailyMetrics: (range: DateRange, signal?: AbortSignal): Promise<DailyMetricsResponse> =>
    request("dailyMetrics", rangeQuery(range), adaptDailyMetrics, signal),

  getErrorDistribution: (range: DateRange, signal?: AbortSignal): Promise<ErrorDistributionResponse> =>
    request("errorDistribution", rangeQuery(range), adaptErrorDistribution, signal),

  getTimeOfDay: (range: DateRange, signal?: AbortSignal): Promise<TimeOfDayResponse> =>
    request("timeOfDay", rangeQuery(range), adaptTimeOfDay, signal),

  getForecastHistory: (range: DateRange, signal?: AbortSignal): Promise<ForecastHistoryResponse> =>
    request("forecastHistory", rangeQuery(range), adaptForecastHistory, signal),

  getDataQuality: (range: DateRange, signal?: AbortSignal): Promise<DataQualityResponse> =>
    request("dataQuality", rangeQuery(range), adaptDataQuality, signal),
};
