import { useEffect, useMemo, useState } from "react";
import { DataState } from "../components/DataState";
import { ForecastActualChart } from "../components/ForecastActualChart";
import { IntervalDetail } from "../components/IntervalDetail";
import { IntervalTable } from "../components/IntervalTable";
import { PageHeader } from "../components/PageHeader";
import { useFilters } from "../context/FilterContext";
import { useAnalytics } from "../hooks/useAnalytics";
import { analyticsApi } from "../services/analyticsApi";
import type { DateRange, IntervalRecord } from "../types";
import { addDays, daysInclusive, formatCount, formatDate, formatRange, listDates, marketDate } from "../utils/format";

/** Interval-level views match the maximum filter range. */
const MAX_MONITOR_DAYS = 92;
const ALL = "all";

export function ForecastMonitorPage() {
  const { range } = useFilters();
  const [focus, setFocus] = useState<string>(ALL);
  const [selected, setSelected] = useState<IntervalRecord | null>(null);

  const tooLong = daysInclusive(range) > MAX_MONITOR_DAYS;
  const effective = useMemo<DateRange>(
    () => (tooLong ? { start: addDays(range.end, -(MAX_MONITOR_DAYS - 1)), end: range.end } : range),
    [range, tooLong],
  );

  useEffect(() => setFocus(ALL), [effective.start, effective.end]);

  const intervals = useAnalytics(
    (signal) => analyticsApi.getIntervals(effective, signal),
    [effective.start, effective.end],
  );

  const dates = useMemo(() => listDates(effective), [effective]);

  return (
    <>
      <PageHeader title="Forecast monitor">
        Forecast and actual wind generation (MW) by delivery time. Choose a single delivery date to focus the chart and
        table, and select any interval to see its details.
      </PageHeader>

      <DataState
        state={intervals.state}
        onRetry={intervals.refetch}
        subject="forecast intervals"
        loadingVariant="block"
        isEmpty={(d) => d.intervals.length === 0}
        partial={(d) =>
          d.intervals.some((r) => r.forecast_mw === null || r.actual_mw === null)
            ? ["Some intervals have no forecast or no actual value. They are shown as unavailable, not as zero error."]
            : []
        }
      >
        {(d) => {
          const rows = focus === ALL ? d.intervals : d.intervals.filter((r) => marketDate(r.delivery_time) === focus);
          const label = focus === ALL ? formatRange(effective) : formatDate(focus);
          return (
            <>
              <div className="filterbar">
                <div className="field">
                  <label htmlFor="focus-date">Delivery date</label>
                  <select id="focus-date" className="input" value={focus} onChange={(e) => setFocus(e.target.value)}>
                    <option value={ALL}>All days in range</option>
                    {dates.map((day) => (
                      <option key={day} value={day}>
                        {formatDate(day)}
                      </option>
                    ))}
                  </select>
                </div>
                <p className="muted" role="status">
                  {formatCount(rows.length)} intervals in the data for {label}. (Days with clock changes have more or
                  fewer than usual.)
                </p>
              </div>

              <section className="card" aria-label="Forecast and actual time series">
                <div className="card__head">
                  <h2>Forecast vs actual</h2>
                  <span className="card__sub">{label}</span>
                </div>
                {rows.length === 0 ? (
                  <div className="state" role="status">
                    <span className="state__title">No intervals for {label}</span>
                    <span className="state__detail">The backend returned no records for this delivery date.</span>
                  </div>
                ) : (
                  <ForecastActualChart
                    intervals={rows}
                    onSelect={setSelected}
                    ariaLabel={`Forecast and actual wind generation in MW for ${label}`}
                  />
                )}
              </section>

              {rows.length > 0 && (
                <IntervalTable
                  rows={rows}
                  variant="monitor"
                  caption={`Interval-level forecast, actual and signed error for ${label}`}
                  onSelect={setSelected}
                />
              )}
            </>
          );
        }}
      </DataState>

      {selected !== null && <IntervalDetail record={selected} onClose={() => setSelected(null)} />}
    </>
  );
}
