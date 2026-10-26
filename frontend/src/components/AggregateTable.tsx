import { formatCount, formatMw, formatPct } from "../utils/format";
import { SignedValue } from "./SignedValue";
import type { TrendDatum, TrendMode } from "./ErrorTrendChart";

interface AggregateTableProps {
  rows: TrendDatum[];
  mode: TrendMode;
  rowHeader: string;
  valueHeader: string;
  caption: string;
}

/**
 * Text alternative to an aggregate chart. Every aggregated figure is listed with
 * its sample count (n), exactly as returned by the backend.
 */
export function AggregateTable({ rows, mode, rowHeader, valueHeader, caption }: AggregateTableProps) {
  const showCoverage = rows.some((r) => r.coveragePct !== undefined);
  return (
    <details>
      <summary className="muted" style={{ cursor: "pointer" }}>
        Show values and sample counts as a table
      </summary>
      <div className="table-wrap" style={{ marginTop: 8, maxHeight: 320, overflow: "auto" }}>
        <table className="table">
          <caption>{caption}</caption>
          <thead>
            <tr>
              <th scope="col">{rowHeader}</th>
              <th scope="col" className="num">{valueHeader}</th>
              {mode !== "count" && <th scope="col" className="num">Sample count (n)</th>}
              {showCoverage && <th scope="col" className="num">Coverage</th>}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key}>
                <th scope="row">{r.label}</th>
                <td className="num">
                  {mode === "signed" ? (
                    <SignedValue value={r.value} />
                  ) : mode === "count" ? (
                    formatCount(r.value)
                  ) : (
                    formatMw(r.value)
                  )}
                </td>
                {mode !== "count" && <td className="num">{formatCount(r.sampleCount)}</td>}
                {showCoverage && <td className="num">{formatPct(r.coveragePct ?? null)}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
