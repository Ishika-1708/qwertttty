interface ChartLegendProps {
  /** "forecast-actual" for line charts, "bar" for aggregate bar charts. */
  kind: "forecast-actual" | "bar";
  barLabel?: string;
}

export function ChartLegend({ kind, barLabel }: ChartLegendProps) {
  if (kind === "bar") {
    return (
      <div className="legend" aria-label="Legend">
        <span className="legend__item">
          <span className="legend__swatch legend__swatch--bar" style={{ background: "var(--series-error)" }} aria-hidden="true" />
          <span className="legend__text">{barLabel}</span>
        </span>
      </div>
    );
  }
  return (
    <div className="legend" aria-label="Legend">
      <span className="legend__item">
        <span className="legend__swatch legend__swatch--forecast" aria-hidden="true" />
        <span className="legend__text">Forecast (solid line)</span>
      </span>
      <span className="legend__item">
        <span className="legend__swatch legend__swatch--actual" aria-hidden="true" />
        <span className="legend__text">Actual (dashed line)</span>
      </span>
    </div>
  );
}
