/**
 * Display formatting only. Nothing here calculates a metric; it turns values
 * the backend returned into text. `null` always renders as "Unavailable" - never
 * as 0 - so a missing value cannot be mistaken for a perfect forecast.
 */
import type { DateRange, IsoDate, IsoTimestamp } from "../types";

export const UNAVAILABLE = "Unavailable";
const LOCALE = "en-GB";
/** GB energy market time. Delivery times are always shown in this zone. */
export const MARKET_TZ = "Europe/London";

/* ------------------------------ numbers ------------------------------ */

export function formatNumber(v: number | null, digits = 1): string {
  if (v === null) return UNAVAILABLE;
  return v.toLocaleString(LOCALE, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function formatMw(v: number | null, digits = 1): string {
  return v === null ? UNAVAILABLE : `${formatNumber(v, digits)} MW`;
}

/** "+12.3 MW" / "-4.1 MW" / "0.0 MW". */
export function formatSignedMw(v: number | null, digits = 1): string {
  if (v === null) return UNAVAILABLE;
  const text = v.toLocaleString(LOCALE, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
    signDisplay: "exceptZero",
  });
  return `${text} MW`;
}

export function formatCount(v: number | null): string {
  return v === null ? UNAVAILABLE : v.toLocaleString(LOCALE);
}

/** `pct` is already a 0-100 figure from the backend; this only formats it. */
export function formatPct(pct: number | null, digits = 1): string {
  return pct === null ? UNAVAILABLE : `${formatNumber(pct, digits)}%`;
}

/* ------------------------------ error direction ------------------------------ */

export type ErrorDirection = "over" | "under" | "none";

/** Direction of a backend-supplied signed error (forecast - actual). Label only. */
export function errorDirection(v: number | null): ErrorDirection | null {
  if (v === null) return null;
  if (v > 0) return "over";
  if (v < 0) return "under";
  return "none";
}

export const DIRECTION_LABEL: Record<ErrorDirection, string> = {
  over: "Forecast above actual",
  under: "Forecast below actual",
  none: "Forecast equal to actual",
};

export const DIRECTION_MARKER: Record<ErrorDirection, string> = { over: "▲", under: "▼", none: "●" };

/* ------------------------------ time ------------------------------ */

const dateTimeFmt = new Intl.DateTimeFormat(LOCALE, {
  timeZone: MARKET_TZ,
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});
const timeFmt = new Intl.DateTimeFormat(LOCALE, { timeZone: MARKET_TZ, hour: "2-digit", minute: "2-digit", hour12: false });
const shortDayFmt = new Intl.DateTimeFormat(LOCALE, { timeZone: MARKET_TZ, day: "2-digit", month: "short" });
const isoDateFmt = new Intl.DateTimeFormat("en-CA", { timeZone: MARKET_TZ, year: "numeric", month: "2-digit", day: "2-digit" });

export function formatDateTime(iso: IsoTimestamp | null): string {
  if (iso === null) return UNAVAILABLE;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? UNAVAILABLE : dateTimeFmt.format(d);
}

export function formatTime(ms: number): string {
  return timeFmt.format(new Date(ms));
}

/** Axis tick for a timestamp: "dd Mon" at midnight, "HH:mm" otherwise. */
export function formatTick(ms: number): string {
  const t = timeFmt.format(new Date(ms));
  return t === "00:00" ? shortDayFmt.format(new Date(ms)) : t;
}

/** Local settlement date ("YYYY-MM-DD", Europe/London) of an ISO timestamp. */
export function marketDate(iso: IsoTimestamp): IsoDate {
  return isoDateFmt.format(new Date(iso));
}

export function formatDate(date: IsoDate): string {
  const d = parseDate(date);
  return d === null ? date : d.toLocaleDateString(LOCALE, { timeZone: "UTC", weekday: "short", day: "2-digit", month: "short", year: "numeric" });
}

export function formatShortDate(date: IsoDate): string {
  const d = parseDate(date);
  return d === null ? date : d.toLocaleDateString(LOCALE, { timeZone: "UTC", day: "2-digit", month: "short" });
}

export function formatRange(range: DateRange): string {
  return range.start === range.end ? formatDate(range.start) : `${formatDate(range.start)} → ${formatDate(range.end)}`;
}

/** "3 min ago" - display of staleness only. */
export function formatAge(iso: IsoTimestamp | null, now: number = Date.now()): string {
  if (iso === null) return UNAVAILABLE;
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return UNAVAILABLE;
  const secs = Math.max(0, Math.round((now - t) / 1000));
  if (secs < 60) return "just now";
  const mins = Math.round(secs / 60);
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours} h ago`;
  return `${Math.round(hours / 24)} days ago`;
}

/* ------------------------------ date arithmetic (calendar dates, no zones) ------------------------------ */

function parseDate(date: IsoDate): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date);
  if (!m) return null;
  return new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])));
}

function toIsoDate(d: Date): IsoDate {
  return d.toISOString().slice(0, 10);
}

export function addDays(date: IsoDate, days: number): IsoDate {
  const d = parseDate(date);
  if (d === null) return date;
  d.setUTCDate(d.getUTCDate() + days);
  return toIsoDate(d);
}

/** Whole calendar days in an inclusive range (calendar arithmetic, not interval counts). */
export function daysInclusive(range: DateRange): number {
  const a = parseDate(range.start);
  const b = parseDate(range.end);
  if (a === null || b === null) return 0;
  return Math.round((b.getTime() - a.getTime()) / 86_400_000) + 1;
}

export function listDates(range: DateRange): IsoDate[] {
  const n = daysInclusive(range);
  return Array.from({ length: Math.max(0, n) }, (_, i) => addDays(range.start, i));
}

/** Default range: the last `days` complete market days, ending yesterday. */
export function defaultRange(days = 7, now: Date = new Date()): DateRange {
  const today = isoDateFmt.format(now);
  const end = addDays(today, -1);
  return { start: addDays(end, -(days - 1)), end };
}

export function isValidRange(range: DateRange): boolean {
  return parseDate(range.start) !== null && parseDate(range.end) !== null && range.start <= range.end;
}
