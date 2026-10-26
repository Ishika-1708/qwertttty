import { useEffect, useState } from "react";
import type { IntervalRecord, IntervalStatus } from "../types";
import { UNAVAILABLE, formatCount, formatDateTime, formatNumber } from "../utils/format";
import { SignedValue } from "./SignedValue";

/** Rows per page in the table (a UI setting; unrelated to how many intervals a day has). */
const PAGE_SIZE = 50;

export type IntervalTableVariant = "monitor" | "history";

interface IntervalTableProps {
  rows: IntervalRecord[];
  variant: IntervalTableVariant;
  caption: string;
  onSelect: (row: IntervalRecord) => void;
}

const STATUS_LABEL: Record<IntervalStatus, string> = {
  matched: "Matched",
  missing_actual: "Missing actual",
  missing_forecast: "Missing forecast",
  unmatched: "Unmatched",
  excluded: "Excluded",
  invalid: "Invalid",
  unknown: "Unknown",
};

function Value({ v }: { v: number | null }) {
  return v === null ? <span className="unavailable">{UNAVAILABLE}</span> : <>{formatNumber(v, 1)}</>;
}

function Eligibility({ value }: { value: boolean | null }) {
  if (value === null) return <span className="unavailable">{UNAVAILABLE}</span>;
  return value ? (
    <span className="tag tag--ok">✓ Available by cutoff</span>
  ) : (
    <span className="tag tag--warn">✕ Published after cutoff</span>
  );
}

export function IntervalTable({ rows, variant, caption, onSelect }: IntervalTableProps) {
  const [page, setPage] = useState(0);
  const pageCount = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));

  // A new data set (different dates) starts at the first page.
  useEffect(() => setPage(0), [rows]);

  const safePage = Math.min(page, pageCount - 1);
  const first = safePage * PAGE_SIZE;
  const visible = rows.slice(first, first + PAGE_SIZE);
  const history = variant === "history";

  return (
    <div className="table-wrap">
      <table className="table">
        <caption>{caption}</caption>
        <thead>
          <tr>
            <th scope="col">Delivery time (UK)</th>
            {history && <th scope="col">Forecast published</th>}
            {history && <th scope="col">Decision cutoff</th>}
            <th scope="col" className="num">Forecast (MW)</th>
            <th scope="col" className="num">Actual (MW)</th>
            <th scope="col" className="num" title="Signed error = forecast − actual. ▲ forecast above actual, ▼ forecast below actual.">
              Error (MW) = forecast − actual
            </th>
            {!history && <th scope="col">Forecast published</th>}
            {history ? <th scope="col">Eligibility</th> : <th scope="col">Status</th>}
          </tr>
        </thead>
        <tbody>
          {visible.map((r) => (
            <tr
              key={r.delivery_time}
              data-clickable="true"
              tabIndex={0}
              onClick={() => onSelect(r)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onSelect(r);
                }
              }}
              aria-label={`Open interval ${formatDateTime(r.delivery_time)}`}
            >
              <td>{formatDateTime(r.delivery_time)}</td>
              {history && <td>{formatDateTime(r.forecast_published_at)}</td>}
              {history && <td>{formatDateTime(r.decision_cutoff_at)}</td>}
              <td className="num"><Value v={r.forecast_mw} /></td>
              <td className="num"><Value v={r.actual_mw} /></td>
              <td className="num"><SignedValue value={r.error_mw} /></td>
              {!history && <td>{formatDateTime(r.forecast_published_at)}</td>}
              <td>
                {history ? (
                  <Eligibility value={r.available_by_cutoff} />
                ) : (
                  <span className={r.status === "matched" ? "tag tag--ok" : "tag tag--warn"}>{STATUS_LABEL[r.status]}</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="table__foot">
        <span className="muted">
          Showing {formatCount(rows.length === 0 ? 0 : first + 1)}–{formatCount(first + visible.length)} of {formatCount(rows.length)} intervals
        </span>
        <span className="segmented" role="group" aria-label="Table pages">
          <button type="button" onClick={() => setPage(safePage - 1)} disabled={safePage === 0}>
            ← Previous
          </button>
          <button type="button" onClick={() => setPage(safePage + 1)} disabled={safePage >= pageCount - 1}>
            Next →
          </button>
        </span>
        <span className="muted">
          Page {safePage + 1} of {pageCount}
        </span>
      </div>
    </div>
  );
}
