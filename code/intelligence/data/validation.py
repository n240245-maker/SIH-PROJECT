"""Deterministic Day-1 integrity and data-quality validation."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Callable

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from .config import load_settings
from .loader import OperationalDataBundle, load_operational_data
from .paths import ProjectPaths
from .schemas import OPERATIONAL_SCHEMAS


class Severity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


def _json_value(value: Any) -> Any:
    if value is None or value is pd.NA:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    return value


class ValidationIssue(BaseModel):
    issue_code: str
    severity: Severity
    file_or_table: str
    record_id: str | None = None
    work_id: str | None = None
    field: str | None = None
    observed_value: Any = None
    expected_condition: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


@dataclass(slots=True)
class ValidationResult:
    as_of_date: date
    source_files_loaded: list[str]
    row_counts: dict[str, int]
    schema_status: dict[str, str]
    key_integrity_summary: dict[str, dict[str, Any]]
    relationship_summary: dict[str, dict[str, Any]]
    quality_summary: dict[str, Any]
    issues: list[ValidationIssue]

    @property
    def issue_counts_by_severity(self) -> dict[str, int]:
        counts = Counter(issue.severity.value for issue in self.issues)
        return {severity.value: counts.get(severity.value, 0) for severity in Severity}

    @property
    def issue_counts_by_code(self) -> dict[str, int]:
        return dict(sorted(Counter(issue.issue_code for issue in self.issues).items()))

    def summary_dict(self) -> dict[str, Any]:
        return {
            "as_of_date": self.as_of_date.isoformat(),
            "source_files_loaded": self.source_files_loaded,
            "row_counts": self.row_counts,
            "schema_status": self.schema_status,
            "key_integrity_summary": self.key_integrity_summary,
            "relationship_summary": self.relationship_summary,
            "quality_summary": self.quality_summary,
            "issue_counts_by_severity": self.issue_counts_by_severity,
            "issue_counts_by_code": self.issue_counts_by_code,
        }


def _issue_for_row(
    frame: pd.DataFrame,
    index: Any,
    *,
    issue_code: str,
    severity: Severity,
    table: str,
    id_field: str,
    field: str | None,
    expected_condition: str,
    message: str,
    work_field: str | None = "work_id",
    observed_value: Any = None,
    details: dict[str, Any] | None = None,
) -> ValidationIssue:
    record_id = _json_value(frame.at[index, id_field]) if id_field in frame.columns else None
    work_id = (
        _json_value(frame.at[index, work_field])
        if work_field is not None and work_field in frame.columns
        else None
    )
    if observed_value is None and field is not None and field in frame.columns:
        observed_value = frame.at[index, field]
    return ValidationIssue(
        issue_code=issue_code,
        severity=severity,
        file_or_table=table,
        record_id=None if record_id is None else str(record_id),
        work_id=None if work_id is None else str(work_id),
        field=field,
        observed_value=_json_value(observed_value),
        expected_condition=expected_condition,
        message=message,
        details={key: _json_value(value) for key, value in (details or {}).items()},
    )


def _validate_primary_keys(
    bundle: OperationalDataBundle,
    issues: list[ValidationIssue],
) -> dict[str, dict[str, Any]]:
    specifications = (
        ("mp", bundle.mp, "mp_id", "mp_id", None),
        ("entities", bundle.entities, "entity_id", "entity_id", None),
        ("works", bundle.works, "work_id", "work_id", "work_id"),
        ("payments", bundle.payments, "payment_id", "payment_id", "work_id"),
        ("progress", bundle.progress, "progress_id", "progress_id", "work_id"),
        ("assets", bundle.assets, "asset_id", "asset_id", "work_id"),
        ("assets", bundle.assets, "work_id", "asset_id", "work_id"),
    )
    summary: dict[str, dict[str, Any]] = {}
    for table, frame, key, id_field, work_field in specifications:
        null_mask = frame[key].isna()
        duplicate_extra_mask = frame[key].notna() & frame[key].duplicated(keep="first")
        duplicate_rows = frame[key].notna() & frame[key].duplicated(keep=False)
        summary[f"{table}.{key}"] = {
            "rows": len(frame),
            "null_count": int(null_mask.sum()),
            "duplicate_extra_count": int(duplicate_extra_mask.sum()),
            "duplicate_row_count": int(duplicate_rows.sum()),
            "status": "PASS" if not null_mask.any() and not duplicate_extra_mask.any() else "FAIL",
        }
        for index in frame.index[null_mask]:
            issues.append(
                _issue_for_row(
                    frame,
                    index,
                    issue_code="NULL_PRIMARY_KEY",
                    severity=Severity.ERROR,
                    table=table,
                    id_field=id_field,
                    field=key,
                    work_field=work_field,
                    expected_condition=f"{key} must be non-null",
                    message=f"Required primary key {key} is null.",
                )
            )
        for index in frame.index[duplicate_extra_mask]:
            issues.append(
                _issue_for_row(
                    frame,
                    index,
                    issue_code="DUPLICATE_PRIMARY_KEY",
                    severity=Severity.ERROR,
                    table=table,
                    id_field=id_field,
                    field=key,
                    work_field=work_field,
                    expected_condition=f"{key} must be unique",
                    message=f"Required primary key {key} duplicates an earlier row.",
                )
            )
    return summary


def _check_relationship(
    *,
    relationship_name: str,
    child_table: str,
    child: pd.DataFrame,
    child_id_field: str,
    child_work_field: str | None,
    foreign_key: str,
    parent: pd.DataFrame,
    parent_key: str,
    issues: list[ValidationIssue],
    parent_filter: pd.Series | None = None,
    null_allowed: pd.Series | None = None,
) -> dict[str, Any]:
    all_parent_ids = set(parent[parent_key].dropna())
    allowed_parent = parent if parent_filter is None else parent.loc[parent_filter]
    allowed_parent_ids = set(allowed_parent[parent_key].dropna())

    non_null = child[foreign_key].notna()
    matched = non_null & child[foreign_key].isin(allowed_parent_ids)
    orphan = non_null & ~child[foreign_key].isin(all_parent_ids)
    unexpected_type = non_null & child[foreign_key].isin(all_parent_ids) & ~child[foreign_key].isin(
        allowed_parent_ids
    )
    allowed_null = (
        pd.Series(False, index=child.index, dtype=bool)
        if null_allowed is None
        else null_allowed.fillna(False).astype(bool)
    )
    invalid_null = child[foreign_key].isna() & ~allowed_null

    for index in child.index[orphan]:
        issues.append(
            _issue_for_row(
                child,
                index,
                issue_code="ORPHAN_FOREIGN_KEY",
                severity=Severity.ERROR,
                table=child_table,
                id_field=child_id_field,
                field=foreign_key,
                work_field=child_work_field,
                expected_condition=f"{foreign_key} must reference {relationship_name}",
                message=f"Foreign key {foreign_key} does not exist in the required parent table.",
            )
        )
    for index in child.index[unexpected_type]:
        issues.append(
            _issue_for_row(
                child,
                index,
                issue_code="FOREIGN_KEY_UNEXPECTED_ENTITY_TYPE",
                severity=Severity.ERROR,
                table=child_table,
                id_field=child_id_field,
                field=foreign_key,
                work_field=child_work_field,
                expected_condition=f"{foreign_key} must reference the expected entity type",
                message=f"Foreign key {foreign_key} resolves to an unexpected entity type.",
            )
        )
    for index in child.index[invalid_null]:
        issues.append(
            _issue_for_row(
                child,
                index,
                issue_code="NULL_REQUIRED_FOREIGN_KEY",
                severity=Severity.ERROR,
                table=child_table,
                id_field=child_id_field,
                field=foreign_key,
                work_field=child_work_field,
                expected_condition=f"{foreign_key} must be populated for this record state",
                message=f"Required foreign key {foreign_key} is null for this record state.",
            )
        )

    return {
        "total_rows": len(child),
        "non_null_references": int(non_null.sum()),
        "matched_references": int(matched.sum()),
        "unmatched_references": int(orphan.sum()),
        "unexpected_entity_type_references": int(unexpected_type.sum()),
        "null_references": int(child[foreign_key].isna().sum()),
        "invalid_null_references": int(invalid_null.sum()),
        "match_percentage_non_null": round(100 * matched.sum() / max(1, non_null.sum()), 6),
        "status": "PASS"
        if not orphan.any() and not unexpected_type.any() and not invalid_null.any()
        else "FAIL",
    }


def _validate_relationships(
    bundle: OperationalDataBundle,
    issues: list[ValidationIssue],
) -> dict[str, dict[str, Any]]:
    entities = bundle.entities
    agency_filter = entities["entity_type"].eq("IMPLEMENTING_AGENCY")
    vendor_filter = entities["entity_type"].eq("VENDOR")
    return {
        "works.mp_id->mp.mp_id": _check_relationship(
            relationship_name="mp.mp_id",
            child_table="works",
            child=bundle.works,
            child_id_field="work_id",
            child_work_field="work_id",
            foreign_key="mp_id",
            parent=bundle.mp,
            parent_key="mp_id",
            issues=issues,
        ),
        "works.implementing_agency_id->entities.entity_id[IMPLEMENTING_AGENCY]": _check_relationship(
            relationship_name="entities.entity_id",
            child_table="works",
            child=bundle.works,
            child_id_field="work_id",
            child_work_field="work_id",
            foreign_key="implementing_agency_id",
            parent=entities,
            parent_key="entity_id",
            parent_filter=agency_filter,
            null_allowed=bundle.works["sanction_status"].isin(["Pending", "Rejected"]),
            issues=issues,
        ),
        "payments.work_id->works.work_id": _check_relationship(
            relationship_name="works.work_id",
            child_table="payments",
            child=bundle.payments,
            child_id_field="payment_id",
            child_work_field="work_id",
            foreign_key="work_id",
            parent=bundle.works,
            parent_key="work_id",
            issues=issues,
        ),
        "payments.vendor_id->entities.entity_id[VENDOR]": _check_relationship(
            relationship_name="entities.entity_id",
            child_table="payments",
            child=bundle.payments,
            child_id_field="payment_id",
            child_work_field="work_id",
            foreign_key="vendor_id",
            parent=entities,
            parent_key="entity_id",
            parent_filter=vendor_filter,
            issues=issues,
        ),
        "payments.authorized_by_agency_id->entities.entity_id[IMPLEMENTING_AGENCY]": _check_relationship(
            relationship_name="entities.entity_id",
            child_table="payments",
            child=bundle.payments,
            child_id_field="payment_id",
            child_work_field="work_id",
            foreign_key="authorized_by_agency_id",
            parent=entities,
            parent_key="entity_id",
            parent_filter=agency_filter,
            issues=issues,
        ),
        "progress.work_id->works.work_id": _check_relationship(
            relationship_name="works.work_id",
            child_table="progress",
            child=bundle.progress,
            child_id_field="progress_id",
            child_work_field="work_id",
            foreign_key="work_id",
            parent=bundle.works,
            parent_key="work_id",
            issues=issues,
        ),
        "progress.reported_by_agency_id->entities.entity_id[IMPLEMENTING_AGENCY]": _check_relationship(
            relationship_name="entities.entity_id",
            child_table="progress",
            child=bundle.progress,
            child_id_field="progress_id",
            child_work_field="work_id",
            foreign_key="reported_by_agency_id",
            parent=entities,
            parent_key="entity_id",
            parent_filter=agency_filter,
            issues=issues,
        ),
        "assets.work_id->works.work_id": _check_relationship(
            relationship_name="works.work_id",
            child_table="assets",
            child=bundle.assets,
            child_id_field="asset_id",
            child_work_field="work_id",
            foreign_key="work_id",
            parent=bundle.works,
            parent_key="work_id",
            issues=issues,
        ),
    }


def _emit_mask(
    *,
    frame: pd.DataFrame,
    mask: pd.Series,
    issues: list[ValidationIssue],
    issue_code: str,
    severity: Severity,
    table: str,
    id_field: str,
    field: str,
    expected_condition: str,
    message: str,
    work_field: str | None = "work_id",
    details_factory: Callable[[Any], dict[str, Any]] | None = None,
) -> None:
    for index in frame.index[mask.fillna(False)]:
        issues.append(
            _issue_for_row(
                frame,
                index,
                issue_code=issue_code,
                severity=severity,
                table=table,
                id_field=id_field,
                field=field,
                work_field=work_field,
                expected_condition=expected_condition,
                message=message,
                details={} if details_factory is None else details_factory(index),
            )
        )


def _validate_ranges_and_amounts(
    bundle: OperationalDataBundle,
    issues: list[ValidationIssue],
) -> None:
    range_specs = (
        (bundle.works, "works", "work_id", "current_physical_progress_pct", 0, 100, "work_id"),
        (bundle.progress, "progress", "progress_id", "physical_progress_pct", 0, 100, "work_id"),
        (
            bundle.progress,
            "progress",
            "progress_id",
            "expected_progress_pct_by_date",
            0,
            100,
            "work_id",
        ),
        (bundle.works, "works", "work_id", "latitude", -90, 90, "work_id"),
        (bundle.works, "works", "work_id", "longitude", -180, 180, "work_id"),
        (bundle.progress, "progress", "progress_id", "geo_latitude", -90, 90, "work_id"),
        (bundle.progress, "progress", "progress_id", "geo_longitude", -180, 180, "work_id"),
    )
    for frame, table, id_field, field, lower, upper, work_field in range_specs:
        mask = ~frame[field].between(lower, upper, inclusive="both")
        _emit_mask(
            frame=frame,
            mask=mask,
            issues=issues,
            issue_code="VALUE_OUT_OF_RANGE",
            severity=Severity.ERROR,
            table=table,
            id_field=id_field,
            field=field,
            work_field=work_field,
            expected_condition=f"{lower} <= {field} <= {upper}",
            message=f"{field} is outside its allowed structural range.",
        )

    financial_over = bundle.progress["financial_progress_pct"].gt(100)
    _emit_mask(
        frame=bundle.progress,
        mask=financial_over,
        issues=issues,
        issue_code="FINANCIAL_PROGRESS_OVER_100",
        severity=Severity.WARNING,
        table="progress",
        id_field="progress_id",
        field="financial_progress_pct",
        expected_condition="financial_progress_pct <= 100 for ordinary utilization",
        message="Financial progress exceeds 100 and requires later business-rule interpretation.",
    )

    monetary_fields = (
        (bundle.mp, "mp", "mp_id", None, "annual_entitlement_inr"),
        (bundle.mp, "mp", "mp_id", None, "allocated_limit_inr"),
        (bundle.mp, "mp", "mp_id", None, "calamity_consent_amount_inr"),
        (bundle.works, "works", "work_id", "work_id", "recommended_amount_inr"),
        (bundle.works, "works", "work_id", "work_id", "technical_estimate_amount_inr"),
        (bundle.works, "works", "work_id", "work_id", "sanctioned_amount_inr"),
        (bundle.works, "works", "work_id", "work_id", "current_expenditure_inr"),
        (bundle.payments, "payments", "payment_id", "work_id", "payment_amount_inr"),
        (bundle.payments, "payments", "payment_id", "work_id", "cumulative_expenditure_inr"),
        (bundle.assets, "assets", "asset_id", "work_id", "final_expenditure_inr"),
    )
    for frame, table, id_field, work_field, field in monetary_fields:
        _emit_mask(
            frame=frame,
            mask=frame[field].lt(0),
            issues=issues,
            issue_code="NEGATIVE_MONETARY_VALUE",
            severity=Severity.WARNING,
            table=table,
            id_field=id_field,
            field=field,
            work_field=work_field,
            expected_condition=f"{field} >= 0",
            message=f"{field} is negative and requires source review.",
        )


def _chronology_issue(
    *,
    frame: pd.DataFrame,
    mask: pd.Series,
    issues: list[ValidationIssue],
    code: str,
    table: str,
    id_field: str,
    field: str,
    comparison_field: str,
    work_field: str | None = "work_id",
) -> None:
    _emit_mask(
        frame=frame,
        mask=mask,
        issues=issues,
        issue_code=code,
        severity=Severity.WARNING,
        table=table,
        id_field=id_field,
        field=field,
        work_field=work_field,
        expected_condition=f"{field} >= {comparison_field}",
        message=f"{field} occurs before {comparison_field}.",
        details_factory=lambda index: {
            field: frame.at[index, field],
            comparison_field: frame.at[index, comparison_field],
        },
    )


def _validate_chronology(
    bundle: OperationalDataBundle,
    as_of_date: date,
    issues: list[ValidationIssue],
) -> None:
    works = bundle.works
    payments = bundle.payments
    progress = bundle.progress
    assets = bundle.assets

    _chronology_issue(
        frame=works,
        mask=works["sanction_date"].lt(works["recommendation_date"]),
        issues=issues,
        code="SANCTION_BEFORE_RECOMMENDATION",
        table="works",
        id_field="work_id",
        field="sanction_date",
        comparison_field="recommendation_date",
    )
    _chronology_issue(
        frame=works,
        mask=works["expected_completion_date"].lt(works["expected_start_date"]),
        issues=issues,
        code="EXPECTED_COMPLETION_BEFORE_START",
        table="works",
        id_field="work_id",
        field="expected_completion_date",
        comparison_field="expected_start_date",
    )
    _chronology_issue(
        frame=works,
        mask=works["actual_start_date"].lt(works["sanction_date"]),
        issues=issues,
        code="ACTUAL_START_BEFORE_SANCTION",
        table="works",
        id_field="work_id",
        field="actual_start_date",
        comparison_field="sanction_date",
    )

    _chronology_issue(
        frame=payments,
        mask=payments["authorization_date"].lt(payments["payment_request_date"]),
        issues=issues,
        code="PAYMENT_AUTH_BEFORE_REQUEST",
        table="payments",
        id_field="payment_id",
        field="authorization_date",
        comparison_field="payment_request_date",
    )
    _chronology_issue(
        frame=payments,
        mask=payments["payment_release_date"].lt(payments["authorization_date"]),
        issues=issues,
        code="PAYMENT_RELEASE_BEFORE_AUTH",
        table="payments",
        id_field="payment_id",
        field="payment_release_date",
        comparison_field="authorization_date",
    )

    recommendation = progress["work_id"].map(works.set_index("work_id")["recommendation_date"])
    sanction = progress["work_id"].map(works.set_index("work_id")["sanction_date"])
    actual_start = progress["work_id"].map(works.set_index("work_id")["actual_start_date"])
    progress_dates = progress["report_date"]
    progress_checks = (
        ("PROGRESS_BEFORE_RECOMMENDATION", recommendation, "recommendation_date"),
        ("PROGRESS_BEFORE_SANCTION", sanction, "sanction_date"),
        ("PROGRESS_BEFORE_ACTUAL_START", actual_start, "actual_start_date"),
    )
    for code, reference, reference_name in progress_checks:
        mask = reference.notna() & progress_dates.lt(reference)
        _emit_mask(
            frame=progress,
            mask=mask,
            issues=issues,
            issue_code=code,
            severity=Severity.WARNING,
            table="progress",
            id_field="progress_id",
            field="report_date",
            expected_condition=f"report_date >= works.{reference_name}",
            message=f"Progress report date occurs before the work {reference_name}.",
            details_factory=lambda index, ref=reference, ref_name=reference_name: {
                "report_date": progress.at[index, "report_date"],
                ref_name: ref.at[index],
            },
        )

    completion = progress["work_id"].map(assets.set_index("work_id")["completion_date"])
    after_completion = completion.notna() & progress_dates.gt(completion)
    _emit_mask(
        frame=progress,
        mask=after_completion,
        issues=issues,
        issue_code="PROGRESS_AFTER_COMPLETION",
        severity=Severity.WARNING,
        table="progress",
        id_field="progress_id",
        field="report_date",
        expected_condition="report_date <= assets.completion_date when completion exists",
        message="Progress report date occurs after the recorded completion date.",
        details_factory=lambda index: {
            "report_date": progress.at[index, "report_date"],
            "completion_date": completion.at[index],
        },
    )

    asset_pairs = (
        ("completion_marked_date", "completion_date"),
        ("utilization_certificate_date", "completion_date"),
        ("handover_date", "completion_date"),
        ("public_use_date", "completion_date"),
        ("audit_date", "completion_date"),
    )
    for field, reference in asset_pairs:
        _chronology_issue(
            frame=assets,
            mask=assets[field].notna() & assets[field].lt(assets[reference]),
            issues=issues,
            code="ASSET_DATE_ORDER_INCONSISTENCY",
            table="assets",
            id_field="asset_id",
            field=field,
            comparison_field=reference,
        )

    as_of_timestamp = pd.Timestamp(as_of_date)
    future_specs = (
        (works, "works", "work_id", "work_id", "actual_start_date"),
        (payments, "payments", "payment_id", "work_id", "payment_request_date"),
        (payments, "payments", "payment_id", "work_id", "authorization_date"),
        (payments, "payments", "payment_id", "work_id", "payment_release_date"),
        (progress, "progress", "progress_id", "work_id", "report_date"),
        (assets, "assets", "asset_id", "work_id", "completion_date"),
        (assets, "assets", "asset_id", "work_id", "completion_marked_date"),
        (assets, "assets", "asset_id", "work_id", "utilization_certificate_date"),
        (assets, "assets", "asset_id", "work_id", "handover_date"),
        (assets, "assets", "asset_id", "work_id", "public_use_date"),
        (assets, "assets", "asset_id", "work_id", "audit_date"),
    )
    for frame, table, id_field, work_field, field in future_specs:
        _emit_mask(
            frame=frame,
            mask=frame[field].notna() & frame[field].gt(as_of_timestamp),
            issues=issues,
            issue_code="FUTURE_ACTUAL_EVENT",
            severity=Severity.WARNING,
            table=table,
            id_field=id_field,
            field=field,
            work_field=work_field,
            expected_condition=f"{field} <= AS_OF_DATE ({as_of_date.isoformat()})",
            message=f"Recorded event date {field} is later than the configured as-of date.",
            details_factory=lambda index, current_field=field, current_frame=frame: {
                current_field: current_frame.at[index, current_field],
                "as_of_date": as_of_date,
            },
        )


def _validate_progress_sequence(
    progress: pd.DataFrame,
    issues: list[ValidationIssue],
) -> dict[str, int]:
    ordered = progress.sort_values(
        ["work_id", "report_date", "progress_id"], kind="stable"
    ).copy()
    ordered["previous_progress"] = ordered.groupby("work_id")["physical_progress_pct"].shift()
    ordered["previous_date"] = ordered.groupby("work_id")["report_date"].shift()
    ordered["change"] = ordered["physical_progress_pct"] - ordered["previous_progress"]
    decrease = ordered["change"].lt(0)
    for index in ordered.index[decrease]:
        issues.append(
            _issue_for_row(
                ordered,
                index,
                issue_code="PHYSICAL_PROGRESS_DECREASE",
                severity=Severity.WARNING,
                table="progress",
                id_field="progress_id",
                field="physical_progress_pct",
                expected_condition="physical progress should ordinarily be non-decreasing by report order",
                message="Physical progress is lower than the preceding report for the same work.",
                details={
                    "previous_progress": ordered.at[index, "previous_progress"],
                    "current_progress": ordered.at[index, "physical_progress_pct"],
                    "previous_date": ordered.at[index, "previous_date"],
                    "current_date": ordered.at[index, "report_date"],
                    "change": ordered.at[index, "change"],
                },
            )
        )

    same_day_extra = progress.duplicated(["work_id", "report_date"], keep="first")
    _emit_mask(
        frame=progress,
        mask=same_day_extra,
        issues=issues,
        issue_code="DUPLICATE_WORK_REPORT_DATE",
        severity=Severity.WARNING,
        table="progress",
        id_field="progress_id",
        field="report_date",
        expected_condition="one progress snapshot per work and report date unless revisions are explicit",
        message="Another progress snapshot exists for the same work and report date.",
    )
    return {
        "physical_progress_decrease_transitions": int(decrease.sum()),
        "physical_progress_decrease_works": int(ordered.loc[decrease, "work_id"].nunique()),
        "same_work_report_date_duplicate_extras": int(same_day_extra.sum()),
    }


def _validate_payments(
    bundle: OperationalDataBundle,
    issues: list[ValidationIssue],
) -> dict[str, int]:
    payments = bundle.payments
    works = bundle.works

    duplicate_pfms = payments["pfms_reference"].notna() & payments["pfms_reference"].duplicated(
        keep="first"
    )
    _emit_mask(
        frame=payments,
        mask=duplicate_pfms,
        issues=issues,
        issue_code="DUPLICATE_PFMS_REFERENCE",
        severity=Severity.WARNING,
        table="payments",
        id_field="payment_id",
        field="pfms_reference",
        expected_condition="pfms_reference should ordinarily identify one payment",
        message="PFMS reference duplicates an earlier payment record.",
    )

    zero_released = payments["payment_status"].eq("Released") & payments["payment_amount_inr"].eq(0)
    _emit_mask(
        frame=payments,
        mask=zero_released,
        issues=issues,
        issue_code="ZERO_RELEASED_PAYMENT",
        severity=Severity.WARNING,
        table="payments",
        id_field="payment_id",
        field="payment_amount_inr",
        expected_condition="released payment amount should ordinarily be greater than zero",
        message="Released payment has a zero amount.",
    )

    payment_totals = payments.groupby("work_id")["payment_amount_inr"].sum()
    works_with_payments = works["work_id"].isin(payment_totals.index)
    observed_totals = works["work_id"].map(payment_totals)
    total_mismatch = works_with_payments & observed_totals.ne(works["current_expenditure_inr"])
    for index in works.index[total_mismatch]:
        issues.append(
            _issue_for_row(
                works,
                index,
                issue_code="PAYMENT_TOTAL_MISMATCH",
                severity=Severity.WARNING,
                table="works",
                id_field="work_id",
                field="current_expenditure_inr",
                expected_condition="sum(payment_amount_inr) == current_expenditure_inr",
                message="Summed payment amounts do not equal the work current expenditure.",
                details={
                    "payment_sum": observed_totals.at[index],
                    "current_expenditure_inr": works.at[index, "current_expenditure_inr"],
                },
            )
        )

    # Day 1.1 audit: payment_stage is a contiguous Stage N sequence for every
    # payment-bearing work and agrees with the sequence suffixes in payment_id,
    # invoice_number, and original source order. Release dates never decrease in
    # that sequence. Authorization/request dates can move backward and therefore
    # must not reorder payments that share a release date.
    payment_stage_sequence = pd.to_numeric(
        payments["payment_stage"].str.extract(r"^Stage\s+(\d+)$", expand=False),
        errors="coerce",
    )
    ordered = payments.assign(_payment_stage_sequence=payment_stage_sequence).sort_values(
        [
            "work_id",
            "payment_release_date",
            "_payment_stage_sequence",
            "payment_id",
        ],
        kind="stable",
        na_position="last",
    )
    ordered["calculated_cumulative_expenditure_inr"] = ordered.groupby("work_id")[
        "payment_amount_inr"
    ].cumsum()
    cumulative_mismatch = ordered["cumulative_expenditure_inr"].ne(
        ordered["calculated_cumulative_expenditure_inr"]
    )
    for index in ordered.index[cumulative_mismatch]:
        issues.append(
            _issue_for_row(
                ordered,
                index,
                issue_code="PAYMENT_CUMULATIVE_MISMATCH",
                severity=Severity.WARNING,
                table="payments",
                id_field="payment_id",
                field="cumulative_expenditure_inr",
                expected_condition=(
                    "reported cumulative expenditure equals payment cumsum ordered by "
                    "release date, natural Stage N sequence, and payment_id"
                ),
                message=(
                    "Reported cumulative expenditure differs from the calculated "
                    "canonical payment sequence total."
                ),
                details={
                    "reported_cumulative_expenditure_inr": ordered.at[
                        index, "cumulative_expenditure_inr"
                    ],
                    "calculated_cumulative_expenditure_inr": ordered.at[
                        index, "calculated_cumulative_expenditure_inr"
                    ],
                },
            )
        )

    return {
        "duplicate_pfms_reference_extras": int(duplicate_pfms.sum()),
        "zero_value_released_payments": int(zero_released.sum()),
        "works_with_payment_total_mismatch": int(total_mismatch.sum()),
        "payment_rows_with_cumulative_mismatch": int(cumulative_mismatch.sum()),
    }


def _validate_status_consistency(
    bundle: OperationalDataBundle,
    issues: list[ValidationIssue],
) -> dict[str, int]:
    works = bundle.works
    payment_counts = bundle.payments.groupby("work_id").size()
    not_started = works["current_status"].eq("Sanctioned - Not Started")
    progress_evidence = works["current_physical_progress_pct"].gt(0)
    expenditure_evidence = works["current_expenditure_inr"].gt(0)
    payment_evidence = works["work_id"].map(payment_counts).fillna(0).gt(0)
    inconsistent = not_started & (progress_evidence | expenditure_evidence | payment_evidence)

    for index in works.index[inconsistent]:
        issues.append(
            _issue_for_row(
                works,
                index,
                issue_code="STATUS_EXECUTION_INCONSISTENCY",
                severity=Severity.WARNING,
                table="works",
                id_field="work_id",
                field="current_status",
                expected_condition="Sanctioned - Not Started should have no execution evidence",
                message="Work status is not-started while one or more execution-evidence conditions are present.",
                details={
                    "nonzero_physical_progress": bool(progress_evidence.at[index]),
                    "nonzero_expenditure": bool(expenditure_evidence.at[index]),
                    "payment_count": int(payment_counts.get(works.at[index, "work_id"], 0)),
                },
            )
        )
    return {
        "sanctioned_not_started_works": int(not_started.sum()),
        "with_nonzero_physical_progress": int((not_started & progress_evidence).sum()),
        "with_nonzero_expenditure": int((not_started & expenditure_evidence).sum()),
        "with_payment_rows": int((not_started & payment_evidence).sum()),
        "with_any_execution_evidence": int(inconsistent.sum()),
    }


def validate_operational_data(
    bundle: OperationalDataBundle,
    *,
    as_of_date: date,
) -> ValidationResult:
    """Validate loaded tables without mutating or merging their source records."""

    issues: list[ValidationIssue] = []
    key_summary = _validate_primary_keys(bundle, issues)
    relationship_summary = _validate_relationships(bundle, issues)
    _validate_ranges_and_amounts(bundle, issues)
    _validate_chronology(bundle, as_of_date, issues)
    progress_summary = _validate_progress_sequence(bundle.progress, issues)
    payment_summary = _validate_payments(bundle, issues)
    status_summary = _validate_status_consistency(bundle, issues)

    progress_counts = bundle.progress.groupby("work_id").size().reindex(
        bundle.works["work_id"], fill_value=0
    )
    quality_summary = {
        "progress_sequence": progress_summary,
        "payment_consistency": payment_summary,
        "status_consistency": status_summary,
        "progress_report_cardinality": {
            "works_with_zero_reports": int(progress_counts.eq(0).sum()),
            "works_with_one_report": int(progress_counts.eq(1).sum()),
            "works_with_multiple_reports": int(progress_counts.gt(1).sum()),
            "minimum": int(progress_counts.min()),
            "median": float(progress_counts.median()),
            "mean": float(progress_counts.mean()),
            "maximum": int(progress_counts.max()),
        },
    }
    schema_status = {schema.table_name: "PASS" for schema in OPERATIONAL_SCHEMAS}
    return ValidationResult(
        as_of_date=as_of_date,
        source_files_loaded=bundle.source_files,
        row_counts=bundle.row_counts,
        schema_status=schema_status,
        key_integrity_summary=key_summary,
        relationship_summary=relationship_summary,
        quality_summary=quality_summary,
        issues=issues,
    )


def validate_evaluation_ground_truth(
    frame: pd.DataFrame,
    *,
    works: pd.DataFrame | None = None,
) -> list[ValidationIssue]:
    """EVALUATION ONLY: validate label-table keys without exposing labels operationally."""

    issues: list[ValidationIssue] = []
    null_key = frame["work_id"].isna()
    duplicate_key = frame["work_id"].notna() & frame["work_id"].duplicated(keep="first")
    risk_out_of_range = ~frame["expected_risk_score_0_100"].between(0, 100, inclusive="both")
    for mask, code, field, condition, message in (
        (null_key, "NULL_PRIMARY_KEY", "work_id", "work_id must be non-null", "Evaluation work_id is null."),
        (
            duplicate_key,
            "DUPLICATE_PRIMARY_KEY",
            "work_id",
            "work_id must be unique",
            "Evaluation work_id duplicates an earlier row.",
        ),
        (
            risk_out_of_range,
            "VALUE_OUT_OF_RANGE",
            "expected_risk_score_0_100",
            "0 <= expected_risk_score_0_100 <= 100",
            "Evaluation risk score is outside 0-100.",
        ),
    ):
        _emit_mask(
            frame=frame,
            mask=mask,
            issues=issues,
            issue_code=code,
            severity=Severity.ERROR,
            table="ground_truth_evaluation_only",
            id_field="work_id",
            field=field,
            work_field="work_id",
            expected_condition=condition,
            message=message,
        )
    if works is not None:
        orphan = frame["work_id"].notna() & ~frame["work_id"].isin(set(works["work_id"]))
        _emit_mask(
            frame=frame,
            mask=orphan,
            issues=issues,
            issue_code="ORPHAN_FOREIGN_KEY",
            severity=Severity.ERROR,
            table="ground_truth_evaluation_only",
            id_field="work_id",
            field="work_id",
            work_field="work_id",
            expected_condition="evaluation work_id must exist in works",
            message="Evaluation work_id does not exist in the work table.",
        )
    return issues


def main() -> int:
    paths = ProjectPaths.discover()
    settings = load_settings(paths)
    bundle = load_operational_data(paths)
    result = validate_operational_data(bundle, as_of_date=settings.as_of_date)

    from .reports import write_validation_outputs

    summary_path, issues_path = write_validation_outputs(result, paths)
    print(f"Validation summary: {summary_path}")
    print(f"Validation issues: {issues_path}")
    print(f"Issue counts: {result.issue_counts_by_severity}")
    return 1 if result.issue_counts_by_severity[Severity.ERROR.value] else 0


if __name__ == "__main__":
    raise SystemExit(main())
