import type { ReactNode } from "react";
import type { AnalyticsState } from "../hooks/useAnalytics";
import { LoadingState } from "./LoadingState";

interface DataStateProps<T> {
  state: AnalyticsState<T>;
  onRetry: () => void;
  /** Name of the view, used in messages: "forecast intervals". */
  subject: string;
  /** True when the response is valid but contains nothing to show. */
  isEmpty?: (data: T) => boolean;
  emptyDetail?: string;
  /** Messages for valid-but-incomplete data; shown above the content. */
  partial?: (data: T) => string[];
  loadingVariant?: "block" | "lines";
  children: (data: T) => ReactNode;
}

/**
 * Every data view goes through this wrapper so loading, empty, error, not-supported
 * and partial-data states are handled identically and can't be forgotten.
 */
export function DataState<T>({
  state,
  onRetry,
  subject,
  isEmpty,
  emptyDetail,
  partial: _partial,
  loadingVariant = "lines",
  children,
}: DataStateProps<T>) {
  switch (state.status) {
    case "idle":
      return null;

    case "loading":
      return <LoadingState label={`Loading ${subject}…`} variant={loadingVariant} />;

    case "error": {
      const { error } = state;
      if (error.kind === "not_supported") {
        return (
          <div className="state" role="status">
            <span className="state__title">{subject}: not provided by the backend</span>
            <span className="state__detail">
              The analytics service does not currently expose this view, so nothing is shown. This is not an error and
              nothing has been estimated in its place.
            </span>
          </div>
        );
      }
      return (
        <div className="state state--error" role="alert">
          <span className="state__title">
            Could not load {subject}. {error.title}.
          </span>
          <span className="state__detail">{error.message}</span>
          {error.kind !== "config" && (
            <button type="button" className="btn" onClick={onRetry}>
              ↻ Retry
            </button>
          )}
        </div>
      );
    }

    case "success": {
      if (isEmpty?.(state.data)) {
        return (
          <div className="state" role="status">
            <span className="state__title">No {subject} for this period</span>
            <span className="state__detail">
              {emptyDetail ?? "The backend returned no records for the selected dates. Try a different date range."}
            </span>
          </div>
        );
      }
      return <>{children(state.data)}</>;
    }
  }
}
