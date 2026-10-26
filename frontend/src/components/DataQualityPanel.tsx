import type { DataQualityResponse } from "../types";
import { formatCount, formatDateTime, formatPct } from "../utils/format";

interface DataQualityPanelProps {
  quality: DataQualityResponse;
}

interface Item {
  label: string;
  value: string;
}

/** All counts are the backend's; nothing is derived here. */
export function DataQualityPanel({ quality: q }: DataQualityPanelProps) {
  const items: Item[] = [
    { label: "Valid matched intervals", value: formatCount(q.valid_matched_intervals) },
    { label: "Expected intervals", value: formatCount(q.expected_intervals) },
    { label: "Coverage", value: formatPct(q.coverage_pct) },
    { label: "Missing actuals", value: formatCount(q.missing_actuals) },
    { label: "Missing forecasts", value: formatCount(q.missing_forecasts) },
    { label: "Unmatched intervals", value: formatCount(q.unmatched_intervals) },
    { label: "Excluded or invalid records", value: formatCount(q.excluded_or_invalid) },
    { label: "Last successful update", value: formatDateTime(q.last_successful_update_at) },
  ];

  return (
    <section className="card" aria-label="Data quality">
      <div className="card__head">
        <h2>Data quality</h2>
        <span className="card__sub">Counts as reported by the analytics backend</span>
      </div>
      <dl className="dq-grid">
        {items.map((i) => (
          <div key={i.label} className="dq-item">
            <dt>{i.label}</dt>
            <dd>{i.value}</dd>
          </div>
        ))}
      </dl>
      {q.exclusion_reasons.length > 0 && (
        <div>
          <h3>Why records were excluded</h3>
          <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
            {q.exclusion_reasons.map((r) => (
              <li key={r.reason}>
                {r.reason}: <strong>{formatCount(r.count)}</strong>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
