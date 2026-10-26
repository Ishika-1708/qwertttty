import { DIRECTION_LABEL, DIRECTION_MARKER, UNAVAILABLE, errorDirection, formatSignedMw } from "../utils/format";

interface SignedValueProps {
  /** Backend-supplied signed error or bias (forecast - actual). */
  value: number | null;
  digits?: number;
  /** Spell the direction out next to the number. */
  showWord?: boolean;
}

/**
 * Positive vs negative is shown with a marker (▲ / ▼), an explicit sign and, optionally,
 * words - never by colour alone. Missing values read "Unavailable", not 0.
 */
export function SignedValue({ value, digits = 1, showWord = false }: SignedValueProps) {
  const dir = errorDirection(value);
  if (dir === null) return <span className="unavailable">{UNAVAILABLE}</span>;
  return (
    <span className="sign" title={DIRECTION_LABEL[dir]}>
      <span className="sign__marker" aria-hidden="true">
        {DIRECTION_MARKER[dir]}
      </span>
      {formatSignedMw(value, digits)}
      {showWord ? (
        <span className="sign__word">{DIRECTION_LABEL[dir]}</span>
      ) : (
        <span className="sr-only">{DIRECTION_LABEL[dir]}</span>
      )}
    </span>
  );
}
