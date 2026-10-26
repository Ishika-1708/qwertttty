import type { Completeness } from "../types";

interface CompletenessBannerProps {
  completeness: Completeness;
  coveragePct: number | null;
  validIntervals: number | null;
  expectedIntervals: number | null;
  warnings: string[];
}

export function CompletenessBanner(_props: CompletenessBannerProps) {
  // Suppressed warning banner per user request
  return null;
}
