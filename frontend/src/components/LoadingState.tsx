interface LoadingStateProps {
  label?: string;
  /** "block" reserves chart space, "lines" suits cards and tables. */
  variant?: "block" | "lines";
}

export function LoadingState({ label = "Loading data…", variant = "lines" }: LoadingStateProps) {
  return (
    <div className="skeleton" role="status" aria-live="polite" aria-busy="true">
      <span className="sr-only">{label}</span>
      {variant === "block" ? (
        <div className="skeleton__bar skeleton__block" />
      ) : (
        <>
          <div className="skeleton__bar" style={{ width: "40%" }} />
          <div className="skeleton__bar" style={{ width: "90%" }} />
          <div className="skeleton__bar" style={{ width: "70%" }} />
        </>
      )}
    </div>
  );
}
