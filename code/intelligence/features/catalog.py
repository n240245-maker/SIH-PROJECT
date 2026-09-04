"""Auditable definitions for every Day-2 project feature column."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class FeatureDefinition:
    name: str
    category: str
    description: str
    formula_or_source: str
    data_type: str
    model_eligible: bool
    generic_anomaly_eligible: bool
    generic_anomaly_notes: str
    leakage_notes: str


GENERIC_ANOMALY_EXCLUSIONS = {
    "unique_vendor_count_as_of": "Current synthetic data has only 0/1 vendors and no multi-vendor variation.",
    "vendor_hhi_as_of": "Zero variance: HHI is 1.0 for every non-null work in the current snapshot.",
    "final_payment_count_as_of": "Exactly duplicates completion-state routing in the current snapshot.",
    "has_final_payment_as_of": "Exactly duplicates completion-state routing in the current snapshot.",
    "zero_value_released_payment_count_as_of": "Near-zero variance; retain as deterministic payment evidence.",
    "days_since_last_progress_report_as_of": "Zero variance because every visible latest progress report is one day before the snapshot.",
    "same_day_progress_extra_count_as_of": "Near-zero variance; retain as deterministic progress-quality evidence.",
    "asset_record_count_as_of": "Currently equivalent to the binary completion-state routing field.",
    "is_completed_as_of": "Lifecycle routing field; models must be routed by stage before feature selection.",
    "completion_marked_as_of": "Closure/compliance context dominated by the synthetic event-date cutoff.",
    "uc_recorded_as_of": "Zero-variance closure/compliance flag in the current snapshot.",
    "handover_recorded_as_of": "Closure/compliance context dominated by the synthetic event-date cutoff.",
    "public_use_recorded_as_of": "Closure/compliance context dominated by the synthetic event-date cutoff.",
    "audit_recorded_as_of": "Zero-variance closure/compliance flag in the current snapshot.",
    "final_expenditure_inr_as_of": "Completion-specific reconciliation candidate with unverified real multi-asset semantics.",
    "actual_duration_days": "All synthetic completions share 2026-08-31, making current duration distribution generator-dependent.",
    "completion_delay_days": "All synthetic completions share 2026-08-31, making current delay distribution generator-dependent.",
}


def _feature(
    name: str,
    category: str,
    description: str,
    formula_or_source: str,
    data_type: str,
    model_eligible: bool,
    leakage_notes: str = "As-of safe under the documented Day-2 snapshot policy.",
) -> FeatureDefinition:
    generic_anomaly_eligible = model_eligible and name not in GENERIC_ANOMALY_EXCLUSIONS
    return FeatureDefinition(
        name=name,
        category=category,
        description=description,
        formula_or_source=formula_or_source,
        data_type=data_type,
        model_eligible=model_eligible,
        generic_anomaly_eligible=generic_anomaly_eligible,
        generic_anomaly_notes=GENERIC_ANOMALY_EXCLUSIONS.get(
            name,
            (
                "Approved candidate only; lifecycle-specific Day-3 selection is still required."
                if generic_anomaly_eligible
                else "Not in the current generic anomaly candidate pool."
            ),
        ),
        leakage_notes=leakage_notes,
    )


NOT_EVIDENCE = "Context or identifier only; not numeric risk evidence."
SOURCE_SNAPSHOT = (
    "Source-current snapshot may post-date AS_OF_DATE; reconciliation only and not model eligible."
)


FEATURE_DEFINITIONS = (
    _feature("work_id", "identifier", "Canonical work identifier.", "03_works.work_id", "string", False, NOT_EVIDENCE),
    _feature("mp_id", "identifier", "MP identifier linked to the work.", "03_works.mp_id", "string", False, NOT_EVIDENCE),
    _feature("state_name", "context", "Work state context.", "03_works.state_name", "string", False, NOT_EVIDENCE),
    _feature("constituency", "context", "Work constituency context.", "03_works.constituency", "string", False, NOT_EVIDENCE),
    _feature("district", "context", "Work district context.", "03_works.district", "string", False, NOT_EVIDENCE),
    _feature("sector", "context", "Work sector context.", "03_works.sector", "string", False, NOT_EVIDENCE),
    _feature("sub_sector", "context", "Work sub-sector context.", "03_works.sub_sector", "string", False, NOT_EVIDENCE),
    _feature("implementing_agency_id", "identifier", "Implementing-agency identifier.", "03_works.implementing_agency_id", "string", False, NOT_EVIDENCE),
    _feature("sanction_status", "context", "Source sanction disposition.", "03_works.sanction_status", "string", False, "No rejection-event timestamp exists; context only."),
    _feature("source_current_status", "reconciliation", "Unadjusted source current status.", "03_works.current_status", "string", False, SOURCE_SNAPSHOT),
    _feature("feature_snapshot_date", "context", "Controlled feature snapshot date.", "Configured AS_OF_DATE", "date", False, NOT_EVIDENCE),
    _feature("lifecycle_stage", "lifecycle", "Transparent as-of lifecycle bucket.", "PRE_SANCTION if rejected/not sanctioned as of; COMPLETION if completed as of; otherwise EXECUTION", "string", False, "Used for stage-aware routing, not as a standalone risk score."),
    _feature("is_rejected", "lifecycle", "Whether source sanction status is Rejected.", "sanction_status == 'Rejected'", "boolean", False, "No rejection-event timestamp exists; routing/context only."),
    _feature("recommendation_date", "context", "Work recommendation date.", "03_works.recommendation_date", "date", False, NOT_EVIDENCE),
    _feature("sanction_date_as_of", "context", "Sanction date only when visible by snapshot.", "sanction_date where sanction_date <= AS_OF_DATE", "date", False, "Future sanction events are masked."),
    _feature("expected_start_date", "schedule", "Planned start date.", "03_works.expected_start_date", "date", False, "Planned future dates are allowed."),
    _feature("expected_completion_date", "schedule", "Planned completion date.", "03_works.expected_completion_date", "date", False, "Planned future dates are allowed."),
    _feature("actual_start_date_as_of", "schedule", "Actual start date visible by snapshot.", "actual_start_date where actual_start_date <= AS_OF_DATE", "date", False, "Future actual starts are masked."),
    _feature("recommended_amount_inr", "financial", "Recommended work amount.", "03_works.recommended_amount_inr", "integer", True),
    _feature("technical_estimate_amount_inr", "financial", "Technical estimate amount.", "03_works.technical_estimate_amount_inr", "integer", True),
    _feature("sanctioned_amount_inr", "financial", "Sanctioned amount when sanction is visible by snapshot.", "03_works.sanctioned_amount_inr where sanction_date <= AS_OF_DATE", "float", True, "Masked before sanction is known."),
    _feature("estimate_to_recommended_ratio", "financial", "Estimate divided by recommendation.", "technical_estimate_amount_inr / recommended_amount_inr", "float", True, "Null when denominator is not positive."),
    _feature("sanction_to_recommended_ratio", "financial", "Sanction divided by recommendation.", "sanctioned_amount_inr / recommended_amount_inr", "float", True, "Null before sanction or when denominator is not positive."),
    _feature("sanction_to_estimate_ratio", "financial", "Sanction divided by estimate.", "sanctioned_amount_inr / technical_estimate_amount_inr", "float", True, "Null before sanction or when denominator is not positive."),
    _feature("days_recommendation_to_sanction", "financial", "Elapsed days from recommendation to visible sanction.", "sanction_date_as_of - recommendation_date", "float", True),
    _feature("planned_duration_days", "schedule", "Planned duration in days.", "expected_completion_date - expected_start_date", "float", True, "Null when plan dates are absent."),
    _feature("days_sanction_to_expected_start", "schedule", "Days from visible sanction to planned start.", "expected_start_date - sanction_date_as_of", "float", True),
    _feature("released_payment_count_as_of", "payment", "Released payment count visible by snapshot.", "count(payment_id where status Released and release_date <= AS_OF_DATE)", "integer", True),
    _feature("released_payment_total_inr_as_of", "payment", "Preferred as-of expenditure measure.", "sum(payment_amount_inr for visible released payments)", "integer", True),
    _feature("unique_vendor_count_as_of", "payment", "Distinct vendors paid by snapshot.", "nunique(vendor_id for visible released payments)", "integer", True),
    _feature("largest_payment_inr_as_of", "payment", "Largest visible released payment.", "max(payment_amount_inr)", "float", True, "Null when no released payment is visible."),
    _feature("mean_payment_inr_as_of", "payment", "Mean visible released payment.", "mean(payment_amount_inr)", "float", True, "Null when no released payment is visible."),
    _feature("largest_payment_share_as_of", "payment", "Largest payment share of released total.", "largest_payment / released_payment_total", "float", True, "Null when released total is not positive."),
    _feature("vendor_hhi_as_of", "payment", "Concentration of released amounts across vendors.", "sum((vendor released amount / total released amount)^2)", "float", False, "Conceptually useful with real multi-vendor variation; constant in the current snapshot."),
    _feature("first_payment_release_date_as_of", "payment", "First visible release date.", "min(payment_release_date)", "date", False, "Date context; no future release included."),
    _feature("last_payment_release_date_as_of", "payment", "Latest visible release date.", "max(payment_release_date)", "date", False, "Date context; no future release included."),
    _feature("days_since_last_payment_as_of", "payment", "Days since latest visible payment.", "AS_OF_DATE - last_payment_release_date_as_of", "float", True),
    _feature("final_payment_count_as_of", "payment", "Visible payments marked final.", "sum(is_final_payment for visible releases)", "integer", True),
    _feature("has_final_payment_as_of", "payment", "Whether a visible payment is marked final.", "final_payment_count_as_of > 0", "boolean", True),
    _feature("zero_value_released_payment_count_as_of", "payment", "Visible released payments with zero amount.", "count(payment_amount_inr == 0)", "integer", True, "Deterministic evidence only; not proof of wrongdoing."),
    _feature("expenditure_to_sanction_pct_as_of", "financial", "Released expenditure as percent of sanction.", "released_payment_total_inr_as_of / sanctioned_amount_inr * 100", "float", True, "Null before sanction or when sanction is not positive."),
    _feature("financial_overrun_amount_inr_as_of", "financial", "Released spend above sanction, floored at zero.", "max(0, released total - sanctioned amount)", "float", True, "Null before sanction or when sanction is not positive."),
    _feature("financial_overrun_pct_as_of", "financial", "Released spend above sanction as percent.", "max(0, released total - sanction) / sanction * 100", "float", True, "Null before sanction or when sanction is not positive."),
    _feature("progress_report_count_as_of", "progress", "Visible progress report count.", "count(progress_id where report_date <= AS_OF_DATE)", "integer", True),
    _feature("first_progress_report_date_as_of", "progress", "First visible progress date.", "first report_date in stable report order", "date", False, "Date context; no future report included."),
    _feature("latest_progress_report_date_as_of", "progress", "Latest visible progress date.", "last report_date in stable report order", "date", False, "Date context; no future report included."),
    _feature("latest_physical_progress_pct_as_of", "progress", "Latest observed physical progress.", "last physical_progress_pct by report_date, progress_id", "float", True),
    _feature("latest_financial_progress_pct_as_of", "progress", "Latest observed financial progress.", "last financial_progress_pct by report_date, progress_id", "float", True),
    _feature("latest_expected_progress_pct_as_of", "progress", "Expected progress in latest visible report.", "last expected_progress_pct_by_date by report_date, progress_id", "float", True),
    _feature("financial_minus_physical_gap_pct_as_of", "progress", "Latest financial minus physical progress.", "latest financial progress - latest physical progress", "float", True),
    _feature("expected_minus_physical_gap_pct_as_of", "progress", "Latest expected minus physical progress.", "latest expected progress - latest physical progress", "float", True),
    _feature("days_since_last_progress_report_as_of", "progress", "Days since latest visible report.", "AS_OF_DATE - latest progress report date", "float", False, "Constant at one day in the current synthetic snapshot; retain for future snapshots."),
    _feature("physical_progress_decrease_count_as_of", "progress", "Count of negative consecutive physical changes.", "count(diff(physical_progress_pct) < 0) in stable report order", "integer", True, "Possible correction/data-quality evidence; not fraud proof."),
    _feature("max_physical_progress_drop_pct_as_of", "progress", "Largest observed consecutive physical drop.", "max(-diff) where diff < 0", "float", True),
    _feature("same_day_progress_extra_count_as_of", "progress", "Extra reports sharing work and report date.", "count beyond first per work_id/report_date", "integer", True, "Possible revision/data-quality evidence."),
    _feature("physical_progress_velocity_pct_per_30d", "progress", "Observed physical change per 30 elapsed days.", "(latest physical - first physical) / elapsed days * 30", "float", True, "Null with fewer than two distinct report dates; no interpolation."),
    _feature("actual_start_available_as_of", "schedule", "Whether actual start is visible by snapshot.", "actual_start_date <= AS_OF_DATE", "boolean", True),
    _feature("days_since_actual_start_as_of", "schedule", "Days since visible actual start.", "AS_OF_DATE - actual_start_date_as_of", "float", True),
    _feature("days_to_expected_completion_as_of", "schedule", "Signed days from snapshot to planned completion.", "expected_completion_date - AS_OF_DATE", "float", True, "Planned future date is permitted."),
    _feature("overdue_days_as_of", "schedule", "Days past planned completion for works not completed as of.", "max(0, AS_OF_DATE - expected_completion_date) when not completed", "float", True, "Readiness input only; no delayed label or threshold."),
    _feature("schedule_elapsed_ratio_as_of", "schedule", "Fraction of planned window elapsed at snapshot.", "max(0, AS_OF_DATE - expected_start_date) / planned_duration_days", "float", True, "May exceed 1; null when planned duration is not positive."),
    _feature("asset_record_count_as_of", "completion", "Asset rows whose completion is visible by snapshot.", "count(asset_id where completion_date <= AS_OF_DATE)", "integer", True),
    _feature("is_completed_as_of", "completion", "Whether any completion record is visible.", "asset_record_count_as_of > 0", "boolean", True),
    _feature("completion_date_as_of", "completion", "Latest visible completion date across asset rows.", "max(completion_date <= AS_OF_DATE)", "date", False, "Future completions are excluded."),
    _feature("completion_marked_as_of", "completion", "Whether completion marking is visible.", "any(completion_marked_date <= AS_OF_DATE)", "boolean", True),
    _feature("uc_recorded_as_of", "completion", "Whether a UC date is visible.", "any(utilization_certificate_date <= AS_OF_DATE)", "boolean", False, "Zero variance at this snapshot; retain for deterministic compliance intelligence."),
    _feature("handover_recorded_as_of", "completion", "Whether handover is visible.", "any(handover_date <= AS_OF_DATE)", "boolean", True),
    _feature("public_use_recorded_as_of", "completion", "Whether public-use event is visible.", "any(public_use_date <= AS_OF_DATE)", "boolean", True),
    _feature("audit_recorded_as_of", "completion", "Whether audit is visible.", "any(audit_date <= AS_OF_DATE)", "boolean", False, "Zero variance at this snapshot; retain for deterministic compliance intelligence."),
    _feature("final_expenditure_inr_as_of", "completion", "Final expenditure on completion-marked rows visible by snapshot.", "sum(final_expenditure_inr where completion_marked_date <= AS_OF_DATE)", "float", True, "Conservative availability; real multi-asset amount semantics require confirmation."),
    _feature("actual_duration_days", "completion", "Days from visible actual start to completion.", "completion_date_as_of - actual_start_date_as_of", "float", True, "Dashboard/evidence formula is valid, but all synthetic completions share 2026-08-31."),
    _feature("completion_delay_days", "completion", "Signed completion difference from plan.", "completion_date_as_of - expected_completion_date", "float", True, "Useful as evidence; all synthetic completions share 2026-08-31, and no delay label is assigned."),
    _feature("source_current_physical_progress_pct", "reconciliation", "Unadjusted source current physical progress.", "03_works.current_physical_progress_pct", "float", False, SOURCE_SNAPSHOT),
    _feature("source_current_expenditure_inr", "reconciliation", "Unadjusted source current expenditure.", "03_works.current_expenditure_inr", "integer", False, SOURCE_SNAPSHOT),
    _feature("source_vs_asof_expenditure_difference_inr", "reconciliation", "Source spend minus released as-of spend.", "source_current_expenditure_inr - released_payment_total_inr_as_of", "integer", False, SOURCE_SNAPSHOT),
    _feature("source_vs_asof_physical_progress_difference_pct", "reconciliation", "Source physical progress minus latest as-of observation.", "source_current_physical_progress_pct - latest_physical_progress_pct_as_of", "float", False, SOURCE_SNAPSHOT),
)


def build_feature_catalog() -> list[dict[str, object]]:
    """Return JSON-serializable catalog records in output-column order."""

    return [asdict(definition) for definition in FEATURE_DEFINITIONS]


def feature_column_names() -> list[str]:
    return [definition.name for definition in FEATURE_DEFINITIONS]


def feature_catalog_payload(as_of_date: date) -> dict[str, object]:
    """Build the complete artifact payload without reading feature values."""

    catalog = build_feature_catalog()
    return {
        "feature_snapshot_date": as_of_date.isoformat(),
        "artifact_type": "runtime/current as-of project feature snapshot",
        "supervised_training_guardrail": (
            "Not automatically valid for supervised prediction training; historical "
            "time-aware snapshots and leakage-safe outcomes are required."
        ),
        "generic_anomaly_guardrail": (
            "generic_anomaly_eligible defines only the current audited candidate pool; "
            "Day-3 selection must still be explicit and lifecycle-aware."
        ),
        "column_count": len(catalog),
        "model_eligible_feature_count": sum(
            bool(item["model_eligible"]) for item in catalog
        ),
        "generic_anomaly_eligible_feature_count": sum(
            bool(item["generic_anomaly_eligible"]) for item in catalog
        ),
        "features": catalog,
    }
