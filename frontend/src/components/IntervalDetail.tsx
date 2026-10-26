import { useEffect, useRef } from "react";
import type { IntervalRecord } from "../types";
import { UNAVAILABLE, formatDateTime, formatMw } from "../utils/format";
import { SignedValue } from "./SignedValue";

interface IntervalDetailProps {
  record: IntervalRecord;
  onClose: () => void;
}

/** Modal showing everything the backend returned for a single interval. */
export function IntervalDetail({ record, onClose }: IntervalDetailProps) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const eligibility =
    record.available_by_cutoff === null
      ? UNAVAILABLE
      : record.available_by_cutoff
        ? "✓ Available by cutoff"
        : "✕ Published after cutoff";

  return (
    <div className="dialog-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="interval-title">
        <h2 id="interval-title">Interval {formatDateTime(record.delivery_time)}</h2>
        <dl>
          <dt>Forecast</dt>
          <dd>{formatMw(record.forecast_mw)}</dd>
          <dt>Actual</dt>
          <dd>{formatMw(record.actual_mw)}</dd>
          <dt>Error (forecast − actual)</dt>
          <dd>
            <SignedValue value={record.error_mw} showWord />
          </dd>
          <dt>Forecast published</dt>
          <dd>{formatDateTime(record.forecast_published_at)}</dd>
          <dt>Decision cutoff</dt>
          <dd>{formatDateTime(record.decision_cutoff_at)}</dd>
          <dt>Eligibility</dt>
          <dd>{eligibility}</dd>
          <dt>Record status</dt>
          <dd>{record.status.replace(/_/g, " ")}</dd>
          {record.exclusion_reason !== null && (
            <>
              <dt>Reason</dt>
              <dd>{record.exclusion_reason}</dd>
            </>
          )}
        </dl>
        <button ref={closeRef} type="button" className="btn" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );
}
