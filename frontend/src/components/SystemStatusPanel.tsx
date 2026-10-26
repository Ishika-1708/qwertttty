import { useEffect, useId, useRef, useState } from "react";
import { useSystemStatus, type Connectivity } from "../context/StatusContext";
import { describeApiBaseUrl } from "../services/analyticsApi";
import { UNAVAILABLE, formatAge, formatDateTime } from "../utils/format";

const LABEL: Record<Connectivity, string> = {
  checking: "Checking backend…",
  online: "Backend online",
  degraded: "Backend degraded",
  offline: "Backend unreachable",
  unconfigured: "Backend not configured",
};

/** Header status indicator + details popover (connectivity, last retrieval, errors, freshness). */
export function SystemStatusPanel() {
  const status = useSystemStatus();
  const [open, setOpen] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const panelId = useId();
  const rootRef = useRef<HTMLDivElement>(null);

  // Tick so "x min ago" stays honest while the panel is open.
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    const onClick = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [open]);

  const lastSuccessIso = status.lastSuccessAt === null ? null : new Date(status.lastSuccessAt).toISOString();
  const freshness = status.dataAsOf ?? status.health?.last_successful_ingest_at ?? null;
  const baseUrl = describeApiBaseUrl();

  return (
    <div className="status" ref={rootRef}>
      <button
        type="button"
        className="btn status__btn"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((o) => !o)}
      >
        <span className={`status__dot status__dot--${status.connectivity}`} aria-hidden="true" />
        {LABEL[status.connectivity]}
      </button>

      {open && (
        <div className="status__panel" id={panelId} role="region" aria-label="System status">
          <h2>System status</h2>
          <dl style={{ margin: 0, display: "grid", gap: 6 }}>
            <div className="status__row">
              <dt>Connectivity</dt>
              <dd>{LABEL[status.connectivity]}</dd>
            </div>
            <div className="status__row">
              <dt>Backend URL</dt>
              <dd>{baseUrl ?? "Not configured"}</dd>
            </div>
            <div className="status__row">
              <dt>Backend version</dt>
              <dd>{status.health?.version ?? UNAVAILABLE}</dd>
            </div>
            <div className="status__row">
              <dt>Last successful retrieval</dt>
              <dd>
                {formatDateTime(lastSuccessIso)}
                <br />
                <span className="muted">{formatAge(lastSuccessIso, now)}</span>
              </dd>
            </div>
            <div className="status__row">
              <dt>Data freshness (backend data as of)</dt>
              <dd>
                {formatDateTime(freshness)}
                <br />
                <span className="muted">{formatAge(freshness, now)}</span>
              </dd>
            </div>
          </dl>

          <div>
            <h3>Recent API errors or interruptions</h3>
            {status.recentErrors.length === 0 ? (
              <p className="muted">None since this page was opened.</p>
            ) : (
              <ul className="status__errors">
                {status.recentErrors.map((e) => (
                  <li key={`${e.at}-${e.endpoint}`}>
                    {formatDateTime(new Date(e.at).toISOString())} · {e.endpoint} · {e.kind}: {e.message}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <button type="button" className="btn" onClick={status.checkNow}>
            ↻ Check now
          </button>
        </div>
      )}
    </div>
  );
}
