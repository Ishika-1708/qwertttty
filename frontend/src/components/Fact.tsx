import type { ReactNode } from "react";

interface FactProps {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
}

/** Small labelled value used for period, cutoff, coverage and freshness facts. */
export function Fact({ label, value, sub }: FactProps) {
  return (
    <div className="card">
      <span className="fact__label">{label}</span>
      <span className="fact__value">{value}</span>
      {sub !== undefined && <span className="fact__sub">{sub}</span>}
    </div>
  );
}
