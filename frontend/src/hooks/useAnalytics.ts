/**
 * `useAnalytics` - the single way views load data from Module 2.
 *
 * It exposes an explicit state machine, so every view must handle each case:
 *
 *   idle     -> not requested (e.g. disabled)
 *   loading  -> request in flight
 *   success  -> data received (the view decides if it is "empty" or "partial")
 *   error    -> typed ApiError (the view offers a retry via `refetch`)
 *
 * Stale responses are discarded: changing the dependencies aborts the previous
 * request, so a slow answer for an old date range can never overwrite a newer one.
 */
import { useCallback, useEffect, useRef, useState, type DependencyList } from "react";
import { useSystemStatus } from "../context/StatusContext";
import { ApiError, isAbortError, isApiError } from "../services/apiError";

export type AnalyticsState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: T; fetchedAt: number }
  | { status: "error"; error: ApiError };

export interface UseAnalyticsOptions<T> {
  /** Set false to skip the request (state stays "idle"). Default true. */
  enabled?: boolean;
  /** Called after a successful response, e.g. to report data freshness. */
  onSuccess?: (data: T) => void;
}

export interface UseAnalyticsResult<T> {
  state: AnalyticsState<T>;
  refetch: () => void;
}

export function useAnalytics<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  deps: DependencyList,
  options: UseAnalyticsOptions<T> = {},
): UseAnalyticsResult<T> {
  const { enabled = true } = options;
  const { recordSuccess, recordFailure } = useSystemStatus();
  const [state, setState] = useState<AnalyticsState<T>>(enabled ? { status: "loading" } : { status: "idle" });
  const [nonce, setNonce] = useState(0);

  // Keep the latest callbacks without re-triggering the effect.
  const fetcherRef = useRef(fetcher);
  const onSuccessRef = useRef(options.onSuccess);
  fetcherRef.current = fetcher;
  onSuccessRef.current = options.onSuccess;

  useEffect(() => {
    if (!enabled) {
      setState({ status: "idle" });
      return;
    }
    const controller = new AbortController();
    setState({ status: "loading" });

    fetcherRef
      .current(controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        recordSuccess();
        onSuccessRef.current?.(data);
        setState({ status: "success", data, fetchedAt: Date.now() });
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted || isAbortError(e)) return;
        const error = isApiError(e)
          ? e
          : new ApiError("http", e instanceof Error ? e.message : "Unknown error", "unknown");
        recordFailure(error);
        setState({ status: "error", error });
      });

    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, nonce, recordSuccess, recordFailure, ...deps]);

  const refetch = useCallback(() => setNonce((n) => n + 1), []);
  return { state, refetch };
}
