/**
 * One error type for everything that can go wrong talking to Module 2, so the UI
 * can render consistent messages and decide whether a retry makes sense.
 */
export type ApiErrorKind =
  | "config" // VITE_API_BASE_URL missing or invalid
  | "network" // request never reached the backend (offline, DNS, CORS, refused)
  | "timeout" // backend did not answer in time
  | "http" // backend answered with an error status
  | "not_supported" // optional endpoint not exposed by Module 2 (404/501)
  | "invalid_response"; // backend answered 2xx but the body did not match the contract

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number | null;
  readonly endpoint: string;

  constructor(kind: ApiErrorKind, message: string, endpoint: string, status: number | null = null) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
    this.endpoint = endpoint;
  }

  /** Retrying can only help for transient problems. */
  get retryable(): boolean {
    return this.kind === "network" || this.kind === "timeout" || (this.kind === "http" && (this.status ?? 0) >= 500);
  }

  /** Short heading for the error panel. */
  get title(): string {
    switch (this.kind) {
      case "config":
        return "Dashboard is not configured";
      case "network":
        return "Cannot reach the analytics backend";
      case "timeout":
        return "The analytics backend took too long to respond";
      case "not_supported":
        return "Not provided by the backend";
      case "invalid_response":
        return "Unexpected response from the backend";
      case "http":
        return `Backend returned an error${this.status ? ` (${this.status})` : ""}`;
    }
  }
}

export function isApiError(e: unknown): e is ApiError {
  return e instanceof ApiError;
}

export function isAbortError(e: unknown): boolean {
  return e instanceof DOMException && e.name === "AbortError";
}
