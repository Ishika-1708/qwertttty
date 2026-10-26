/**
 * Single source of truth for series styling so forecast and actual look the same
 * on every chart (and match the legend swatches in charts.css).
 *
 * Identity is carried by colour AND line style (solid vs dashed), never colour alone.
 * Colours are CSS variables defined in styles/dashboard.css (light + dark).
 */
export const SERIES = {
  forecast: { key: "forecast_mw", name: "Forecast", stroke: "var(--series-forecast)", strokeWidth: 2, dash: undefined },
  actual: { key: "actual_mw", name: "Actual", stroke: "var(--series-actual)", strokeWidth: 2, dash: "6 4" },
} as const;

/** Fill for aggregated-error bars (distinct from the forecast/actual pair). */
export const ERROR_BAR_FILL = "var(--series-error)";

export const AXIS_STROKE = "var(--axis)";

/**
 * Recharts reports the hovered/clicked point differently across versions
 * (`activeTooltipIndex` vs `activeIndex`, number vs string). Read it defensively.
 */
export function activeIndexFromState(state: unknown): number | null {
  if (typeof state !== "object" || state === null) return null;
  const s = state as { activeTooltipIndex?: unknown; activeIndex?: unknown };
  const raw = s.activeTooltipIndex ?? s.activeIndex;
  const n = typeof raw === "string" ? Number(raw) : raw;
  return typeof n === "number" && Number.isInteger(n) && n >= 0 ? n : null;
}
