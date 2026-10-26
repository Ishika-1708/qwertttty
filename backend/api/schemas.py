"""Pydantic response schemas (the JSON contract for Module 3).

Conventions: all energy values are MW floats; metrics are `null` (never 0) when
sample_count is 0; timestamps are ISO-8601 strings (UTC with 'Z'; *_local carries an offset);
field names are identical across endpoints.
"""
from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from pydantic import BaseModel


class MetricsBlock(BaseModel):
    sample_count: int
    mae_mw: Optional[float]
    rmse_mw: Optional[float]
    mbe_mw: Optional[float]
    mape_pct: Optional[float] = None
    mape_sample_count: Optional[int] = None
    mape_excluded_count: Optional[int] = None


class CoverageBlock(BaseModel):
    expected_intervals: int
    valid_matched_pairs: int
    missing_forecasts: int
    missing_actuals: int
    missing_both: int
    no_eligible_forecasts: int
    invalid_pairs: int
    coverage_pct: Optional[float]


class Period(BaseModel):
    start_date: Optional[date]
    end_date: Optional[date]
    timezone: str
    first_interval_utc: Optional[str]
    last_interval_utc: Optional[str]


class InputCounts(BaseModel):
    forecast_rows: int
    actual_rows: int
    expected_intervals: int


class Traceability(BaseModel):
    dataset_id: str
    dataset_version: str
    calculation_version: str
    pairs_fingerprint: str
    error_definition: str
    forecast_selection_rule: str
    cutoff_rule: str
    unit: str
    aggregation_timezone: str
    input_row_counts: InputCounts


class SummaryResponse(BaseModel):
    period: Period
    metrics: MetricsBlock
    coverage: CoverageBlock
    unit: str
    error_sign_convention: str
    traceability: Traceability


class IntervalItem(BaseModel):
    interval_start_utc: str
    interval_start_local: str
    decision_cutoff_utc: str
    forecast_publish_time_utc: Optional[str]
    lead_time_hours: Optional[float]
    forecast_mw: Optional[float]
    actual_mw: Optional[float]
    error_mw: Optional[float]
    abs_error_mw: Optional[float]
    status: str                      # "valid" | "excluded"
    exclusion_reason: Optional[str]
    exclusion_detail: Optional[str]
    issues: Optional[str]


class IntervalsResponse(BaseModel):
    period: Period
    status_filter: str
    total: int
    limit: int
    offset: int
    items: List[IntervalItem]
    display_timezone: str
    unit: str
    error_sign_convention: str
    traceability: Traceability


class AggregationRow(BaseModel):
    group: str                       # "YYYY-MM-DD" or "HH:MM"
    expected_intervals: int
    sample_count: int
    coverage_pct: Optional[float]
    mae_mw: Optional[float]
    rmse_mw: Optional[float]
    mbe_mw: Optional[float]
    low_sample: bool


class AggregationResponse(BaseModel):
    period: Period
    group_by: str
    bucket_minutes: Optional[int]
    timezone: str
    unit: str
    groups: List[AggregationRow]
    note: str
    error_sign_convention: str
    traceability: Traceability


class DecisionTimeEvaluation(BaseModel):
    basis: str
    metrics: MetricsBlock
    coverage: CoverageBlock


class LeadBucketRow(BaseModel):
    scope: str                       # "pre_cutoff" | "post_cutoff"
    lead_bucket: str
    version_count: int
    interval_count: int
    mae_mw: Optional[float]
    rmse_mw: Optional[float]
    mbe_mw: Optional[float]


class RevisionSummary(BaseModel):
    intervals_with_multiple_versions: int
    mean_abs_revision_mw: float
    mean_signed_revision_mw: float
    mean_abs_error_first_mw: float
    mean_abs_error_decision_mw: float
    improved_count: int
    worsened_count: int
    unchanged_count: int


class RevisionAnalysis(BaseModel):
    status: str                      # "ok" | "no_eligible_data" | "history_unavailable"
    message: Optional[str]
    include_post_cutoff: bool
    lead_bins_hours: List[float]
    versions_considered: int
    by_lead_bucket: List[LeadBucketRow]
    revisions: Optional[RevisionSummary]


class ForecastVersionsResponse(BaseModel):
    period: Period
    decision_time_evaluation: DecisionTimeEvaluation
    revision_analysis: RevisionAnalysis
    unit: str
    note: str
    error_sign_convention: str
    traceability: Traceability


class ExcludedExample(BaseModel):
    interval_start_utc: str
    reason: str
    reason_detail: Optional[str]
    issues: Optional[str]


class DataQualityResponse(BaseModel):
    period: Period
    coverage: CoverageBlock
    exclusions_by_reason: Dict[str, int]
    invalid_detail_counts: Dict[str, int]
    informational: Dict[str, Optional[int]]
    excluded_examples: List[ExcludedExample]
    accounting_note: str
    traceability: Traceability
