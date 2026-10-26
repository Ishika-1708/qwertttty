/**
 * The selected evaluation period, shared by every page so a date change
 * refreshes metrics and charts everywhere.
 */
import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import type { DateRange } from "../types";

interface FilterState {
  range: DateRange;
  setRange: (range: DateRange) => void;
}

const FilterContext = createContext<FilterState | null>(null);

export function FilterProvider({ children }: { children: ReactNode }) {
  // Default to January 2026 matching the Elexon dataset range
  const [range, setRange] = useState<DateRange>({ start: "2026-01-01", end: "2026-01-31" });
  const value = useMemo(() => ({ range, setRange }), [range]);
  return <FilterContext.Provider value={value}>{children}</FilterContext.Provider>;
}

export function useFilters(): FilterState {
  const ctx = useContext(FilterContext);
  if (ctx === null) throw new Error("useFilters must be used inside <FilterProvider>");
  return ctx;
}
