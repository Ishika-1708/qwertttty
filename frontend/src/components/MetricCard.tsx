import { DIRECTION_LABEL, DIRECTION_MARKER, errorDirection, formatCount, formatNumber } from "../utils/format";

interface MetricCardProps {
  label: string;
  /** Value exactly as returned by the backend; null = unavailable. */
  value: number | null;
  unit?: string;
  /** Show an explicit +/- sign and direction (used for MBE). */
  signed?: boolean;
  /** Plain-language explanation shown under the number. */
  explanation: string;
  /** Number of intervals the backend scored to produce this value. */
  sampleCount: number | null;
}

export function MetricCard({ label, value, unit = "MW", signed = false, explanation, sampleCount }: MetricCardProps) {
  const dir = signed ? errorDirection(value) : null;
  const text =
    value === null
      ? "Unavailable"
      : signed
        ? value.toLocaleString("en-GB", { minimumFractionDigits: 1, maximumFractionDigits: 1, signDisplay: "exceptZero" })
        : formatNumber(value, 1);

  return (
    <section className="card" aria-label={label}>
      <span className="metric__label">{label}</span>
      <p className={value === null ? "metric__value metric__value--na" : "metric__value tabular"}>
        {text}
        {value !== null && <span className="metric__unit">{unit}</span>}
      </p>
      {dir !== null && (
        <p className="sign">
          <span className="sign__marker" aria-hidden="true">
            {DIRECTION_MARKER[dir]}
          </span>
          {DIRECTION_LABEL[dir]} on average
        </p>
      )}
      <p className="metric__help">{explanation}</p>
      <p className="metric__n">Based on {formatCount(sampleCount)} matched intervals</p>
    </section>
  );
}
