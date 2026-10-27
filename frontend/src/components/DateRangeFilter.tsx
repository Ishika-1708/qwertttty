import { useEffect, useState } from "react";
import { useFilters } from "../context/FilterContext";
import type { DateRange } from "../types";
import { addDays, daysInclusive, defaultRange, isValidRange } from "../utils/format";

/** UI guard so a mistyped range cannot ask the backend for years of data. */
const MAX_RANGE_DAYS = 92;

export function DateRangeFilter() {
  const { range, setRange } = useFilters();
  const [draft, setDraft] = useState<DateRange>(range);

  // Keep the inputs in step if the range is changed elsewhere (e.g. a preset).
  useEffect(() => setDraft(range), [range]);

  const problem = !isValidRange(draft)
    ? "Start date must be on or before the end date."
    : daysInclusive(draft) > MAX_RANGE_DAYS
      ? `Choose at most ${MAX_RANGE_DAYS} days.`
      : null;
  const unchanged = draft.start === range.start && draft.end === range.end;
  const today = addDays(defaultRange(1).end, 1);

  return (
    <form
      className="filterbar"
      aria-label="Evaluation period"
      onSubmit={(e) => {
        e.preventDefault();
        if (problem === null) setRange(draft);
      }}
    >
      <div className="field">
        <label htmlFor="range-start">Delivery date from</label>
        <input
          id="range-start"
          className="input"
          type="date"
          value={draft.start}
          max={today}
          onChange={(e) => setDraft({ ...draft, start: e.target.value })}
        />
      </div>
      <div className="field">
        <label htmlFor="range-end">to</label>
        <input
          id="range-end"
          className="input"
          type="date"
          value={draft.end}
          max={today}
          onChange={(e) => setDraft({ ...draft, end: e.target.value })}
        />
      </div>
      <button type="submit" className="btn btn--primary" disabled={problem !== null || unchanged}>
        Apply
      </button>

      {problem !== null && (
        <p role="alert" className="muted" style={{ flexBasis: "100%" }}>
          ⚠ {problem}
        </p>
      )}
    </form>
  );
}
