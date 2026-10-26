import { useState } from "react";
import { DataQualityPanel } from "../components/DataQualityPanel";
import { DataState } from "../components/DataState";
import { IntervalDetail } from "../components/IntervalDetail";
import { IntervalTable } from "../components/IntervalTable";
import { PageHeader } from "../components/PageHeader";
import { useFilters } from "../context/FilterContext";
import { useAnalytics } from "../hooks/useAnalytics";
import { analyticsApi } from "../services/analyticsApi";
import type { IntervalRecord } from "../types";
import { UNAVAILABLE, formatCount, formatDateTime, formatRange } from "../utils/format";

export function ForecastHistoryPage() {
  const { range } = useFilters();
  const deps = [range.start, range.end];
  const [selected, setSelected] = useState<IntervalRecord | null>(null);

  const history = useAnalytics((s) => analyticsApi.getForecastHistory(range, s), deps);
  const quality = useAnalytics((s) => analyticsApi.getDataQuality(range, s), deps);
  const intervals = useAnalytics((s) => analyticsApi.getIntervals(range, s), deps);

  return (
    <>
      <PageHeader title="Forecast history & data quality">
        Which forecast was used, when it was published relative to the decision cutoff, and how complete the underlying
        data is. A forecast counts only if it was published at or before the cutoff.
      </PageHeader>

      <section className="card" aria-label="Selected forecast version and decision cutoff">
        <h2>Selected forecast version & decision cutoff</h2>
        <DataState
          state={history.state}
          onRetry={history.refetch}
          subject="forecast history"
          isEmpty={() => false}
        >
          {(h) => (
            <>
              <dl className="dq-grid">
                <div className="dq-item">
                  <dt>Period</dt>
                  <dd style={{ fontSize: 15 }}>{formatRange(h.period)}</dd>
                </div>
                <div className="dq-item">
                  <dt>Decision cutoff</dt>
                  <dd style={{ fontSize: 15 }}>{h.decision_cutoff.description ?? UNAVAILABLE}</dd>
                </div>
                <div className="dq-item">
                  <dt>Selected forecast version</dt>
                  <dd style={{ fontSize: 15 }}>{h.selected_version_description ?? UNAVAILABLE}</dd>
                </div>
              </dl>

              {h.publications.length === 0 ? (
                <p className="muted">No forecast publications were returned for this period.</p>
              ) : (
                <div className="table-wrap" style={{ maxHeight: 320, overflow: "auto" }}>
                  <table className="table">
                    <caption>Forecast publications in this period (as retained)</caption>
                    <thead>
                      <tr>
                        <th scope="col">Published (UK)</th>
                        <th scope="col">Version</th>
                        <th scope="col" className="num">Intervals covered</th>
                        <th scope="col">Used for evaluation</th>
                      </tr>
                    </thead>
                    <tbody>
                      {h.publications.map((p) => (
                        <tr key={`${p.published_at}-${p.version_id ?? ""}`}>
                          <td>{formatDateTime(p.published_at)}</td>
                          <td>{p.version_id ?? UNAVAILABLE}</td>
                          <td className="num">{formatCount(p.intervals_covered)}</td>
                          <td>{p.selected ? <span className="tag tag--ok">✓ Selected</span> : <span className="tag">Not selected</span>}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </DataState>
      </section>

      <DataState state={quality.state} onRetry={quality.refetch} subject="data-quality figures" isEmpty={() => false}>
        {(q) => <DataQualityPanel quality={q} />}
      </DataState>

      <section className="card" aria-label="Interval eligibility">
        <div className="card__head">
          <h2>Interval records and eligibility</h2>
          <span className="card__sub">{formatRange(range)}</span>
        </div>
        <DataState
          state={intervals.state}
          onRetry={intervals.refetch}
          subject="interval records"
          loadingVariant="block"
          isEmpty={(d) => d.intervals.length === 0}
        >
          {(d) => (
            <IntervalTable
              rows={d.intervals}
              variant="history"
              caption="Each interval with its forecast publication time, the decision cutoff, and whether the forecast was available by the cutoff"
              onSelect={setSelected}
            />
          )}
        </DataState>
      </section>

      <p className="muted">
        Forecast-version comparison charts are planned for a later release and depend on Module 1 retaining the
        complete forecast history.
      </p>

      {selected !== null && <IntervalDetail record={selected} onClose={() => setSelected(null)} />}
    </>
  );
}
