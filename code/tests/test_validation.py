"""Integrity, quality-rule, and cardinality regression tests."""

from __future__ import annotations

import pandas as pd

from intelligence.data.validation import Severity, validate_evaluation_ground_truth
from intelligence.data.loader import load_evaluation_ground_truth


def test_required_primary_keys_are_complete_and_unique(validation_result):
    assert validation_result.key_integrity_summary
    for result in validation_result.key_integrity_summary.values():
        assert result["status"] == "PASS"
        assert result["null_count"] == 0
        assert result["duplicate_extra_count"] == 0


def test_major_relationships_have_full_integrity(validation_result):
    expected_relationships = {
        "works.mp_id->mp.mp_id",
        "works.implementing_agency_id->entities.entity_id[IMPLEMENTING_AGENCY]",
        "payments.work_id->works.work_id",
        "payments.vendor_id->entities.entity_id[VENDOR]",
        "payments.authorized_by_agency_id->entities.entity_id[IMPLEMENTING_AGENCY]",
        "progress.work_id->works.work_id",
        "progress.reported_by_agency_id->entities.entity_id[IMPLEMENTING_AGENCY]",
        "assets.work_id->works.work_id",
    }
    assert set(validation_result.relationship_summary) == expected_relationships
    for relationship in validation_result.relationship_summary.values():
        assert relationship["status"] == "PASS"
        assert relationship["unmatched_references"] == 0
        assert relationship["unexpected_entity_type_references"] == 0
        assert relationship["invalid_null_references"] == 0


def test_known_day_05_findings_are_reproduced(validation_result):
    counts = validation_result.issue_counts_by_code
    assert counts["PAYMENT_AUTH_BEFORE_REQUEST"] == 718
    assert counts["PROGRESS_BEFORE_ACTUAL_START"] == 12
    assert counts["FINANCIAL_PROGRESS_OVER_100"] == 4_292
    assert counts["PHYSICAL_PROGRESS_DECREASE"] == 295
    assert counts["DUPLICATE_WORK_REPORT_DATE"] == 13
    assert counts["DUPLICATE_PFMS_REFERENCE"] == 1
    assert counts["ZERO_RELEASED_PAYMENT"] == 4
    assert counts["STATUS_EXECUTION_INCONSISTENCY"] == 10
    assert "PAYMENT_CUMULATIVE_MISMATCH" not in counts
    assert validation_result.issue_counts_by_severity == {
        Severity.ERROR.value: 0,
        Severity.WARNING.value: 13_332,
        Severity.INFO.value: 0,
    }


def test_known_work_level_quality_counts_are_reproduced(validation_result):
    quality = validation_result.quality_summary
    before_start_works = {
        issue.work_id
        for issue in validation_result.issues
        if issue.issue_code == "PROGRESS_BEFORE_ACTUAL_START"
    }
    assert len(before_start_works) == 5
    assert quality["progress_sequence"] == {
        "physical_progress_decrease_transitions": 295,
        "physical_progress_decrease_works": 220,
        "same_work_report_date_duplicate_extras": 13,
    }
    assert quality["status_consistency"] == {
        "sanctioned_not_started_works": 24,
        "with_nonzero_physical_progress": 9,
        "with_nonzero_expenditure": 10,
        "with_payment_rows": 10,
        "with_any_execution_evidence": 10,
    }


def test_payment_consistency_is_calculated(validation_result):
    assert validation_result.quality_summary["payment_consistency"] == {
        "duplicate_pfms_reference_extras": 1,
        "zero_value_released_payments": 4,
        "works_with_payment_total_mismatch": 0,
        "payment_rows_with_cumulative_mismatch": 0,
    }


def test_payment_sequence_audit_supports_release_then_natural_stage(operational_bundle):
    payments = operational_bundle.payments.copy()
    stage_sequence = pd.to_numeric(
        payments["payment_stage"].str.extract(r"^Stage\s+(\d+)$", expand=False),
        errors="coerce",
    )
    payment_id_sequence = pd.to_numeric(
        payments["payment_id"].str.extract(r"-(\d+)$", expand=False),
        errors="coerce",
    )
    invoice_sequence = pd.to_numeric(
        payments["invoice_number"].str.extract(r"-(\d+)$", expand=False),
        errors="coerce",
    )

    assert stage_sequence.notna().all()
    assert stage_sequence.equals(payment_id_sequence)
    assert stage_sequence.equals(invoice_sequence)
    assert not payments.assign(_stage=stage_sequence).duplicated(
        ["work_id", "_stage"], keep=False
    ).any()

    legacy = payments.sort_values(
        [
            "work_id",
            "payment_release_date",
            "authorization_date",
            "payment_request_date",
            "payment_id",
        ],
        kind="stable",
    )
    legacy_mismatch = legacy["cumulative_expenditure_inr"].ne(
        legacy.groupby("work_id")["payment_amount_inr"].cumsum()
    )
    assert int(legacy_mismatch.sum()) == 97
    assert legacy.loc[legacy_mismatch, "work_id"].nunique() == 44

    canonical = payments.assign(_stage=stage_sequence).sort_values(
        ["work_id", "payment_release_date", "_stage", "payment_id"],
        kind="stable",
    )
    canonical_mismatch = canonical["cumulative_expenditure_inr"].ne(
        canonical.groupby("work_id")["payment_amount_inr"].cumsum()
    )
    assert not canonical_mismatch.any()

    source_order_mismatch = payments["cumulative_expenditure_inr"].ne(
        payments.groupby("work_id")["payment_amount_inr"].cumsum()
    )
    assert not source_order_mismatch.any()


def test_naive_three_table_cardinality_is_diagnostic_only(operational_bundle):
    """Compute counts algebraically; never materialize a giant merged table."""

    works = operational_bundle.works
    payment_counts = operational_bundle.payments.groupby("work_id").size()
    progress_counts = operational_bundle.progress.groupby("work_id").size()
    per_work_payments = works["work_id"].map(payment_counts).fillna(0).clip(lower=1)
    per_work_progress = works["work_id"].map(progress_counts).fillna(0).clip(lower=1)

    works_payments_rows = int(per_work_payments.sum())
    works_progress_rows = int(per_work_progress.sum())
    naive_three_table_rows = int((per_work_payments * per_work_progress).sum())

    assert works_payments_rows == 10_011
    assert works_progress_rows == 15_172
    assert naive_three_table_rows == 53_640
    assert round(naive_three_table_rows / len(works), 2) == 17.88


def test_evaluation_ground_truth_integrity_is_checked_separately(
    project_paths,
    operational_bundle,
):
    evaluation = load_evaluation_ground_truth(project_paths)
    issues = validate_evaluation_ground_truth(evaluation, works=operational_bundle.works)
    assert issues == []
