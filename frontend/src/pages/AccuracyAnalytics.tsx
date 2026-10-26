import { useState } from "react";
import { AggregateTable } from "../components/AggregateTable";
import { DataState } from "../components/DataState";
import { ErrorTrendChart, type TrendDatum, type TrendMode } from "../components/ErrorTrendChart";
import { PageHeader } from "../components/PageHeader";
import { useFilters } from "../context/FilterContext";
import { useAnalytics } from "../hooks/useAnalytics";
import { analyticsApi } from "../services/analyticsApi";
import type { DailyMetricsResponse, ErrorDistributionResponse, Metric, TimeOfDayResponse } from "../types";
import { formatCount, formatNumber, formatShortDate } from "../utils/format";

const METRIC_LABEL: Record<Metric, string> = { mae: "MAE", rmse: "RMSE", mbe: "MBE (bias)" };
const METRIC_NAME: Record<Metric, string> = {
  mae: "Mean absolute error (MW)",
  rmse: "Root mean square error (MW)",
  mbe: "Mean bias error (MW)",
};
const modeFor = (m: Metric): TrendMode => (m === "mbe" ? "signed" : "magnitude");

/** Pick the selected metric if the backend returns it, otherwise the first one it does. */
function resolveMetric(selected: Metric, available: Metric[]): Metric | null {
  if (available.includes(selected)) return selected;
  return available[0] ?? null;
}

function MetricSwitch({ available, value, onChange }: { available: Metric[]; value: Metric; onChange: (m: Metric) => void }) {
  if (available.length < 2) return null;
  return (
    <div className="segmented" role="group" aria-label="Metric">
      {available.map((m) => (
        <button key={m} type="button" aria-pressed={m === value} onClick={() => onChange(m)}>
          {METRIC_LABEL[m]}
        </button>
      ))}
    </div>
  );
}

function binLabel(lower: number, upper: number | null): string {
  return upper === null ? `${formatNumber(lower, 0)}+` : `${formatNumber(lower, 0)}–${formatNumber(upper, 0)}`;
}

function dailyData(d: DailyMetricsResponse, metric: Metric): TrendDatum[] {
  return d.points.map((p) => ({
    key: p.date,
    label: formatShortDate(p.date),
    value: p[metric],
    sampleCount: p.sample_count,
    coveragePct: p.coverage_pct,
  }));
}

function distributionData(d: ErrorDistributionResponse): TrendDatum[] {
  return d.bins.map((b) => ({
    key: String(b.lower_mw),
    label: binLabel(b.lower_mw, b.upper_mw),
    value: b.count,
    sampleCount: b.count,
  }));
}

function timeOfDayData(d: TimeOfDayResponse, metric: Metric): TrendDatum[] {
  return d.groups.map((g) => ({ key: g.label, label: g.label, value: g[metric], sampleCount: g.sample_count }));
}

export function AccuracyAnalyticsPage() {
  const { range } = useFilters();
  const [metric, setMetric] = useState<Metric>("mae");
  const deps = [range.start, range.end];

  const daily = useAnalytics((s) => analyticsApi.getDailyMetrics(range, s), deps);
  const distribution = useAnalytics((s) => analyticsApi.getErrorDistribution(range, s), deps);
  const timeOfDay = useAnalytics((s) => analyticsApi.getTimeOfDay(range, s), deps);

  return (
    <>
      <PageHeader title="Accuracy analytics">
        How forecast error behaved over the selected period. Every aggregated figure is shown with the number of
        intervals behind it. These charts show patterns only - they do not explain what caused them.
      </PageHeader>

      <div className="grid grid--two">
        <section className="card" aria-label="Daily error trend">
          <div className="card__head">
            <h2>Daily error trend</h2>
            {daily.state.status === "success" && (
              <MetricSwitch available={daily.state.data.available_metrics} value={metric} onChange={setMetric} />
            )}
          </div>
          <DataState
            state={daily.state}
            onRetry={daily.refetch}
            subject="daily metrics"
            loadingVariant="block"
            isEmpty={(d) => d.points.length === 0}
            partial={(d) =>
              d.available_metrics.length < 3
                ? [`The backend returns only ${d.available_metrics.map((m) => METRIC_LABEL[m]).join(", ") || "no metrics"} here.`]
                : []
            }
          >
            {(d) => {
              const m = resolveMetric(metric, d.available_metrics);
              if (m === null) {
                return (
                  <div className="state" role="status">
                    <span className="state__title">No metric values returned</span>
                    <span className="state__detail">The backend returned daily rows but no values for MAE, RMSE or MBE.</span>
                  </div>
                );
              }
              const data = dailyData(d, m);
              return (
                <>
                  <ErrorTrendChart
                    data={data}
                    mode={modeFor(m)}
                    seriesLabel={METRIC_NAME[m]}
                    yLabel="MW"
                    ariaLabel={`Daily ${METRIC_LABEL[m]} in MW`}
                  />
                  <AggregateTable
                    rows={data}
                    mode={modeFor(m)}
                    rowHeader="Delivery date"
                    valueHeader={METRIC_LABEL[m]}
                    caption={`Daily ${METRIC_LABEL[m]} with sample counts`}
                  />
                </>
              );
            }}
          </DataState>
        </section>

        <section className="card" aria-label="Bias trend">
          <div className="card__head">
            <h2>Bias trend (signed error)</h2>
            <span className="card__sub">Forecast − actual, daily mean</span>
          </div>
          <DataState
            state={daily.state}
            onRetry={daily.refetch}
            subject="daily bias"
            loadingVariant="block"
            isEmpty={(d) => d.points.length === 0}
          >
            {(d) => {
              if (!d.available_metrics.includes("mbe")) {
                return (
                  <div className="state" role="status">
                    <span className="state__title">Bias (MBE) is not returned by the backend</span>
                    <span className="state__detail">Nothing has been estimated in its place.</span>
                  </div>
                );
              }
              const data = dailyData(d, "mbe");
              return (
                <>
                  <ErrorTrendChart
                    data={data}
                    mode="signed"
                    seriesLabel={METRIC_NAME.mbe}
                    yLabel="MW"
                    ariaLabel="Daily mean bias error in MW"
                  />
                  <AggregateTable
                    rows={data}
                    mode="signed"
                    rowHeader="Delivery date"
                    valueHeader="MBE"
                    caption="Daily bias with sample counts"
                  />
                </>
              );
            }}
          </DataState>
        </section>

        <section className="card" aria-label="Absolute error distribution">
          <div className="card__head">
            <h2>Absolute error distribution</h2>
            <span className="card__sub">How many intervals fall in each error size</span>
          </div>
          <DataState
            state={distribution.state}
            onRetry={distribution.refetch}
            subject="error distribution"
            loadingVariant="block"
            isEmpty={(d) => d.bins.length === 0}
          >
            {(d) => {
              const data = distributionData(d);
              return (
                <>
                  <ErrorTrendChart
                    data={data}
                    mode="count"
                    seriesLabel="Intervals (count)"
                    yLabel="Intervals"
                    xLabel="Absolute error (MW)"
                    ariaLabel="Distribution of absolute forecast error in MW"
                  />
                  <p className="chart-note">Sample count (n) for this period: {formatCount(d.total_count)} intervals.</p>
                  <AggregateTable
                    rows={data}
                    mode="count"
                    rowHeader="Absolute error (MW)"
                    valueHeader="Intervals"
                    caption="Interval counts per absolute-error band"
                  />
                </>
              );
            }}
          </DataState>
        </section>

        <section className="card" aria-label="Time-of-day comparison">
          <div className="card__head">
            <h2>Time-of-day comparison</h2>
            <span className="card__sub">Error by time of day, as grouped by the backend</span>
          </div>
          <DataState
            state={timeOfDay.state}
            onRetry={timeOfDay.refetch}
            subject="time-of-day comparison"
            loadingVariant="block"
            isEmpty={(d) => d.groups.length === 0}
          >
            {(d) => {
              const m = resolveMetric(metric, d.available_metrics);
              if (m === null) {
                return (
                  <div className="state" role="status">
                    <span className="state__title">No metric values returned</span>
                  </div>
                );
              }
              const data = timeOfDayData(d, m);
              return (
                <>
                  <ErrorTrendChart
                    data={data}
                    mode={modeFor(m)}
                    seriesLabel={METRIC_NAME[m]}
                    yLabel="MW"
                    xLabel={d.grouping ?? "Time of day (UK)"}
                    ariaLabel={`${METRIC_LABEL[m]} by time of day in MW`}
                  />
                  <AggregateTable
                    rows={data}
                    mode={modeFor(m)}
                    rowHeader="Time of day"
                    valueHeader={METRIC_LABEL[m]}
                    caption={`${METRIC_LABEL[m]} by time of day with sample counts`}
                  />
                </>
              );
            }}
          </DataState>
        </section>
      </div>
    </>
  );
}
