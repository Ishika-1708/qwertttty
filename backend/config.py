"""Central configuration and the calculation version stamp.

Every tunable convention lives here so that it is stated once, echoed in API
responses, and never silently hard-coded in calculation code.
"""
from __future__ import annotations

from dataclasses import dataclass
from zoneinfo import ZoneInfo

# Bump when any calculation, selection rule or validation rule changes.
CALCULATION_VERSION = "2.0.0"

# Human-readable statements echoed in API `traceability` blocks.
ERROR_DEFINITION = "error_mw = forecast_mw - actual_mw (positive = overforecast, negative = underforecast)"
SELECTION_RULE = (
    "For each expected delivery interval the decision-time forecast is the Module 1 un-flagged "
    "version with the latest publish_time_utc that is <= decision_cutoff_utc (inclusive). "
    "No fallback to older versions if that version is unusable; later versions are never used."
)
CUTOFF_RULE = "decision_cutoff_utc is supplied per interval by Module 1; Module 2 never derives it."


@dataclass(frozen=True)
class AnalyticsConfig:
    """Immutable evaluation conventions.

    expected_unit            Only this unit is accepted (case-insensitive). No conversion is done.
    interval_minutes         Length of one delivery interval (Elexon settlement period = 30).
    allow_negative_values    Negative generation/forecast values are invalid unless True.
    aggregation_timezone     THE single timezone used to derive delivery dates and time-of-day
                             buckets. Default UTC. Use "Europe/London" to match Elexon settlement
                             dates (see README, assumption A3).
    display_timezone         Only used to add `interval_start_local` for display; never for grouping.
    mape_min_actual_mw       Actuals below this are excluded from MAPE (reported, never zero-filled).
    low_sample_threshold     Groups with fewer samples are flagged `low_sample` in aggregations.
    default_lead_bins_hours  Edges of lead-time buckets for forecast-revision analysis.
    """

    expected_unit: str = "MW"
    interval_minutes: int = 30
    allow_negative_values: bool = False
    aggregation_timezone: str = "UTC"
    display_timezone: str = "Europe/London"
    mape_min_actual_mw: float = 100.0
    low_sample_threshold: int = 5
    default_lead_bins_hours: tuple = (0, 6, 12, 24, 48, 96)

    def __post_init__(self) -> None:
        for tz in (self.aggregation_timezone, self.display_timezone):
            ZoneInfo(tz)  # raises ZoneInfoNotFoundError for an invalid IANA name
        if self.interval_minutes <= 0 or 1440 % self.interval_minutes != 0:
            raise ValueError("interval_minutes must be a positive divisor of 1440")
        if self.mape_min_actual_mw <= 0:
            raise ValueError("mape_min_actual_mw must be > 0")
