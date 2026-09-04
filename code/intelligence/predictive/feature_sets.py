"""Explicit, audited predictor allowlists for the two Day-6 outcomes."""

from __future__ import annotations


POINT_IN_TIME_PREDICTORS = (
    "recommended_amount_inr",
    "technical_estimate_amount_inr",
    "sanctioned_amount_inr",
    "estimate_to_recommended_ratio",
    "sanction_to_recommended_ratio",
    "sanction_to_estimate_ratio",
    "days_recommendation_to_sanction",
    "planned_duration_days",
    "days_sanction_to_expected_start",
    "released_payment_count_as_of",
    "released_payment_total_inr_as_of",
    "largest_payment_inr_as_of",
    "mean_payment_inr_as_of",
    "largest_payment_share_as_of",
    "days_since_last_payment_as_of",
    "expenditure_to_sanction_pct_as_of",
    "financial_overrun_amount_inr_as_of",
    "financial_overrun_pct_as_of",
    "progress_report_count_as_of",
    "latest_physical_progress_pct_as_of",
    "latest_financial_progress_pct_as_of",
    "latest_expected_progress_pct_as_of",
    "financial_minus_physical_gap_pct_as_of",
    "expected_minus_physical_gap_pct_as_of",
    "physical_progress_decrease_count_as_of",
    "max_physical_progress_drop_pct_as_of",
    "physical_progress_velocity_pct_per_30d",
    "actual_start_available_as_of",
    "days_since_actual_start_as_of",
    "days_to_expected_completion_as_of",
    "schedule_elapsed_ratio_as_of",
    "landmark_fraction",
)

# The target pipelines are intentionally declared independently. They currently
# share the same leakage-safe state variables, but neither list is inferred from
# the 76-column runtime feature table or from the other target.
DELAY_PREDICTORS = tuple([*POINT_IN_TIME_PREDICTORS])
COST_OVERRUN_PREDICTORS = tuple([*POINT_IN_TIME_PREDICTORS])

ABSOLUTE_DATE_FIELDS = {
    "recommendation_date",
    "sanction_date",
    "sanction_date_as_of",
    "expected_start_date",
    "expected_completion_date",
    "actual_start_date",
    "actual_start_date_as_of",
    "completion_date",
    "completion_date_as_of",
    "landmark_date",
}

OUTCOME_OR_RECONCILIATION_FIELDS = {
    "final_expenditure_inr",
    "final_expenditure_inr_as_of",
    "actual_duration_days",
    "completion_delay_days",
    "source_current_physical_progress_pct",
    "source_current_expenditure_inr",
    "source_vs_asof_expenditure_difference_inr",
    "source_vs_asof_physical_progress_difference_pct",
}


def validate_predictor_allowlist(columns: tuple[str, ...]) -> None:
    """Fail closed if an outcome, absolute date, or duplicate field is admitted."""

    if len(columns) != len(set(columns)):
        raise ValueError("Predictor allowlist contains duplicate fields")
    prohibited = (ABSOLUTE_DATE_FIELDS | OUTCOME_OR_RECONCILIATION_FIELDS).intersection(
        columns
    )
    if prohibited:
        raise ValueError(f"Predictor allowlist contains leakage fields: {sorted(prohibited)}")
    fragments = ("injected_anomaly", "expected_risk", "ground_truth", "duplicate_group")
    matched = [
        column for column in columns if any(fragment in column.casefold() for fragment in fragments)
    ]
    if matched:
        raise ValueError(f"Predictor allowlist contains evaluation helper fields: {matched}")


validate_predictor_allowlist(DELAY_PREDICTORS)
validate_predictor_allowlist(COST_OVERRUN_PREDICTORS)
