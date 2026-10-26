/**
 * System status: backend connectivity, last successful retrieval, recent API
 * errors, and data freshness. Fed by (a) a periodic /health poll and (b) every
 * request made through `useAnalytics`.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { analyticsApi } from "../services/analyticsApi";
import { ApiError, isAbortError, isApiError } from "../services/apiError";
import type { HealthResponse } from "../types";

export type Connectivity = "checking" | "online" | "degraded" | "offline" | "unconfigured";

export interface LoggedError {
  at: number; // epoch ms
  endpoint: string;
  kind: ApiError["kind"];
  message: string;
}

export interface SystemStatus {
  connectivity: Connectivity;
  health: HealthResponse | null;
  /** Last time the dashboard received a good response from any endpoint (epoch ms). */
  lastSuccessAt: number | null;
  /** Freshest "data as of" timestamp the backend has reported. */
  dataAsOf: string | null;
  recentErrors: LoggedError[];
  recordSuccess: () => void;
  recordFailure: (error: ApiError) => void;
  reportDataAsOf: (iso: string | null) => void;
  checkNow: () => void;
}

const StatusContext = createContext<SystemStatus | null>(null);

const HEALTH_POLL_MS = 60_000;
const MAX_LOGGED_ERRORS = 8;

export function StatusProvider({ children }: { children: ReactNode }) {
  const [connectivity, setConnectivity] = useState<Connectivity>("checking");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [lastSuccessAt, setLastSuccessAt] = useState<number | null>(null);
  const [dataAsOf, setDataAsOf] = useState<string | null>(null);
  const [recentErrors, setRecentErrors] = useState<LoggedError[]>([]);
  const inFlight = useRef<AbortController | null>(null);

  const recordSuccess = useCallback(() => setLastSuccessAt(Date.now()), []);

  const recordFailure = useCallback((error: ApiError) => {
    // "not supported" is a capability, not an interruption.
    if (error.kind === "not_supported") return;
    setRecentErrors((prev) =>
      [{ at: Date.now(), endpoint: error.endpoint, kind: error.kind, message: error.message }, ...prev].slice(0, MAX_LOGGED_ERRORS),
    );
  }, []);

  const reportDataAsOf = useCallback((iso: string | null) => {
    if (iso !== null) setDataAsOf(iso);
  }, []);

  const checkNow = useCallback(() => {
    inFlight.current?.abort();
    const controller = new AbortController();
    inFlight.current = controller;
    setConnectivity((c) => (c === "online" || c === "degraded" ? c : "checking"));
    analyticsApi
      .getHealth(controller.signal)
      .then((h) => {
        setHealth(h);
        setConnectivity(h.status === "ok" ? "online" : h.status === "down" ? "offline" : "degraded");
        setLastSuccessAt(Date.now());
      })
      .catch((e: unknown) => {
        if (isAbortError(e)) return;
        if (isApiError(e)) {
          setConnectivity(e.kind === "config" ? "unconfigured" : "offline");
          recordFailure(e);
        } else {
          setConnectivity("offline");
        }
      });
  }, [recordFailure]);

  useEffect(() => {
    checkNow();
    const id = window.setInterval(checkNow, HEALTH_POLL_MS);
    return () => {
      window.clearInterval(id);
      inFlight.current?.abort();
    };
  }, [checkNow]);

  const value = useMemo<SystemStatus>(
    () => ({ connectivity, health, lastSuccessAt, dataAsOf, recentErrors, recordSuccess, recordFailure, reportDataAsOf, checkNow }),
    [connectivity, health, lastSuccessAt, dataAsOf, recentErrors, recordSuccess, recordFailure, reportDataAsOf, checkNow],
  );

  return <StatusContext.Provider value={value}>{children}</StatusContext.Provider>;
}

export function useSystemStatus(): SystemStatus {
  const ctx = useContext(StatusContext);
  if (ctx === null) throw new Error("useSystemStatus must be used inside <StatusProvider>");
  return ctx;
}
