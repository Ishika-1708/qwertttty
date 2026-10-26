import { DataState } from "../components/DataState";
import { Fact } from "../components/Fact";
import { ForecastActualChart } from "../components/ForecastActualChart";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { useFilters } from "../context/FilterContext";
import { useSystemStatus } from "../context/StatusContext";
import { useAnalytics } from "../hooks/useAnalytics";
import { analyticsApi } from "../services/analyticsApi";
import {
  UNAVAILABLE,
  formatAge,
  formatCount,
  formatDate,
  formatDateTime,
  formatPct,
  formatRange,
} from "../utils/format";

const EXPLAIN = {
  mae: "Average size of the forecast error, ignoring whether it was too high or too low. In megawatts - not a percentage accuracy score.",
  rmse: "Like MAE, but larger misses count for more. In megawatts - not a percentage accuracy score.",
  mbe: "Average signed error (forecast minus actual). A positive value means forecasts exceeded actual generation on average; a negative value means they fell short.",
} as const;

export function OverviewPage() {
  const { range } = useFilters();
  const { reportDataAsOf } = useSystemStatus();

  const summary = useAnalytics(
    (signal) => analyticsApi.getSummary(range, signal),
    [range.start, range.end],
    { onSuccess: (d) => reportDataAsOf(d.data_as_of) },
  );

  // The compact chart shows the most recent delivery date in the period (one day keeps it readable).
  const latestDay = useAnalytics(
    (signal) => analyticsApi.getIntervals({ start: range.end, end: range.end }, signal),
    [range.end],
  );

  return (
    <>
      <PageHeader title="Executive overview">
        How wind forecasts performed against actual generation, using only the forecasts that were available at the
        purchasing decision cutoff. These figures are evidence for the purchasing team; they are not a recommendation.
      </PageHeader>

      <DataState
        state={summary.state}
        onRetry={summary.refetch}
        subject="summary metrics"
        loadingVariant="lines"
        partial={(d) =>
          (["mae", "rmse", "mbe"] as const)
            .filter((m) => d.metrics[m] === null)
            .map((m) => `${m.toUpperCase()} is unavailable for this period (shown as "Unavailable", not as zero).`)
        }
      >
        {(d) => (
          <>
            <div className="grid grid--kpi">
              <MetricCard label="MAE · mean absolute error" value={d.metrics.mae} explanation={EXPLAIN.mae} sampleCount={d.valid_matched_intervals} />
              <MetricCard label="RMSE · root mean square error" value={d.metrics.rmse} explanation={EXPLAIN.rmse} sampleCount={d.valid_matched_intervals} />
              <MetricCard label="MBE · mean bias error" value={d.metrics.mbe} signed explanation={EXPLAIN.mbe} sampleCount={d.valid_matched_intervals} />
            </div>

            <div className="grid grid--facts">
              <Fact label="Evaluation period" value={formatRange(d.period)} />
              <Fact
                label="Decision cutoff"
                value={d.decision_cutoff.description ?? "Not provided by the backend"}
                sub="Forecasts published after this point are not counted."
              />
              <Fact
                label="Valid matched intervals"
                value={formatCount(d.valid_matched_intervals)}
                sub={`of ${formatCount(d.expected_intervals)} expected`}
              />
              <Fact label="Coverage" value={formatPct(d.coverage_pct)} sub="Reported by the backend" />
              <Fact
                label="Backend data as of"
                value={formatDateTime(d.data_as_of)}
                sub={d.data_as_of === null ? UNAVAILABLE : formatAge(d.data_as_of)}
              />
              <Fact
                label="Dashboard last retrieved"
                value={summary.state.status === "success" ? formatDateTime(new Date(summary.state.fetchedAt).toISOString()) : UNAVAILABLE}
                sub="Last successful request for these figures"
              />
            </div>
          </>
        )}
      </DataState>

      <section className="card" aria-label="Forecast versus actual, latest day">
        <div className="card__head">
          <h2>Forecast vs actual · {formatDate(range.end)}</h2>
          <a href="#/monitor" className="card__sub">
            Open Forecast Monitor →
          </a>
        </div>
        <DataState
          state={latestDay.state}
          onRetry={latestDay.refetch}
          subject="intervals for the latest day"
          loadingVariant="block"
          isEmpty={(d) => d.intervals.length === 0}
          emptyDetail="The backend has no intervals for the last day of the selected period."
          partial={(d) =>
            d.intervals.some((r) => r.forecast_mw === null || r.actual_mw === null)
              ? ["Some intervals on this day have no forecast or no actual value; they appear as gaps."]
              : []
          }
        >
          {(d) => (
            <ForecastActualChart
              intervals={d.intervals}
              size="compact"
              ariaLabel={`Forecast and actual wind generation in MW for ${formatDate(range.end)}`}
            />
          )}
        </DataState>
      </section>
    </>
  );
}
