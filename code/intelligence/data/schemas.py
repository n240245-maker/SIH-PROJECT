"""Exact canonical CSV schemas verified during Day 0 and Day 0.5."""

from __future__ import annotations

from dataclasses import dataclass

import pandera.pandas as pa


@dataclass(frozen=True, slots=True)
class ColumnSpec:
    name: str
    kind: str
    nullable: bool = False


@dataclass(frozen=True, slots=True)
class TableSchema:
    table_name: str
    filename: str
    columns: tuple[ColumnSpec, ...]
    primary_keys: tuple[str, ...]

    @property
    def expected_columns(self) -> list[str]:
        return [column.name for column in self.columns]

    def pandera_schema(self) -> pa.DataFrameSchema:
        dtype_map = {
            "string": pa.String,
            "category": pa.String,
            "integer": pa.Int64,
            "float": pa.Float64,
            "boolean": pa.Bool,
            "date": pa.DateTime,
        }
        return pa.DataFrameSchema(
            {
                column.name: pa.Column(
                    dtype_map[column.kind],
                    nullable=column.nullable,
                    required=True,
                )
                for column in self.columns
            },
            strict=True,
            ordered=True,
            coerce=False,
            name=self.table_name,
        )


def _column(name: str, kind: str = "string", *, nullable: bool = False) -> ColumnSpec:
    return ColumnSpec(name=name, kind=kind, nullable=nullable)


MP_SCHEMA = TableSchema(
    table_name="mp",
    filename="01_mp_master.csv",
    primary_keys=("mp_id",),
    columns=(
        _column("mp_id"),
        _column("mp_name"),
        _column("house_type", "category"),
        _column("tenure"),
        _column("state_code"),
        _column("state_name"),
        _column("constituency"),
        _column("nodal_district"),
        _column("annual_entitlement_inr", "integer"),
        _column("allocated_limit_inr", "integer"),
        _column("calamity_consent_amount_inr", "integer"),
        _column("record_effective_date", "date"),
        _column("source_type"),
        _column("source_reference"),
        _column("synthetic_marker", "boolean"),
    ),
)

ENTITIES_SCHEMA = TableSchema(
    table_name="entities",
    filename="02_agencies_vendors.csv",
    primary_keys=("entity_id",),
    columns=(
        _column("entity_id"),
        _column("entity_type", "category"),
        _column("entity_name"),
        _column("state_name"),
        _column("district"),
        _column("registration_or_office_code"),
        _column("vendor_category", "category", nullable=True),
        _column("active_status", "category"),
        _column("source_type"),
        _column("synthetic_marker", "boolean"),
    ),
)

WORKS_SCHEMA = TableSchema(
    table_name="works",
    filename="03_works.csv",
    primary_keys=("work_id",),
    columns=(
        _column("work_id"),
        _column("mp_id"),
        _column("house_type", "category"),
        _column("tenure"),
        _column("state_name"),
        _column("constituency"),
        _column("nodal_district"),
        _column("recommendation_date", "date"),
        _column("recommendation_type", "category"),
        _column("sector", "category"),
        _column("sub_sector", "category"),
        _column("work_description"),
        _column("work_location_state"),
        _column("district"),
        _column("block"),
        _column("village"),
        _column("latitude", "float"),
        _column("longitude", "float"),
        _column("recommended_amount_inr", "integer"),
        _column("technical_estimate_amount_inr", "integer"),
        _column("sanctioned_amount_inr", "integer"),
        _column("sanction_date", "date", nullable=True),
        _column("sanction_status", "category"),
        _column("implementing_agency_id", nullable=True),
        _column("expected_start_date", "date", nullable=True),
        _column("expected_completion_date", "date", nullable=True),
        _column("actual_start_date", "date", nullable=True),
        _column("current_status", "category"),
        _column("current_physical_progress_pct", "float"),
        _column("current_expenditure_inr", "integer"),
        _column("duplicate_group_reference", nullable=True),
        _column("source_type"),
        _column("source_reference"),
        _column("synthetic_marker", "boolean"),
    ),
)

PAYMENTS_SCHEMA = TableSchema(
    table_name="payments",
    filename="04_payments.csv",
    primary_keys=("payment_id",),
    columns=(
        _column("payment_id"),
        _column("work_id"),
        _column("vendor_id"),
        _column("payment_request_date", "date"),
        _column("authorization_date", "date"),
        _column("payment_release_date", "date"),
        _column("payment_amount_inr", "integer"),
        _column("payment_stage"),
        _column("invoice_number"),
        _column("cumulative_expenditure_inr", "integer"),
        _column("payment_status", "category"),
        _column("payment_mode"),
        _column("pfms_reference"),
        _column("authorized_by_agency_id"),
        _column("concurrence_authority"),
        _column("is_final_payment", "boolean"),
        _column("source_type"),
        _column("synthetic_marker", "boolean"),
    ),
)

PROGRESS_SCHEMA = TableSchema(
    table_name="progress",
    filename="05_progress.csv",
    primary_keys=("progress_id",),
    columns=(
        _column("progress_id"),
        _column("work_id"),
        _column("report_date", "date"),
        _column("physical_progress_pct", "float"),
        _column("financial_progress_pct", "float"),
        _column("expected_progress_pct_by_date", "float"),
        _column("execution_stage", "category"),
        _column("reported_status", "category"),
        _column("reported_by_agency_id"),
        _column("photo_reference"),
        _column("geo_latitude", "float"),
        _column("geo_longitude", "float"),
        _column("remarks"),
        _column("source_type"),
        _column("synthetic_marker", "boolean"),
    ),
)

ASSETS_SCHEMA = TableSchema(
    table_name="assets",
    filename="06_assets_compliance.csv",
    primary_keys=("asset_id", "work_id"),
    columns=(
        _column("work_id"),
        _column("completion_date", "date"),
        _column("completion_marked_date", "date"),
        _column("final_expenditure_inr", "integer"),
        _column("utilization_certificate_status", "category"),
        _column("utilization_certificate_date", "date", nullable=True),
        _column("asset_id"),
        _column("asset_type"),
        _column("user_agency"),
        _column("asset_register_entry", "category"),
        _column("handover_date", "date"),
        _column("public_use_date", "date"),
        _column("audit_status", "category"),
        _column("audit_date", "date", nullable=True),
        _column("audit_observation_category"),
        _column("compliance_status", "category"),
        _column("maintenance_agency"),
        _column("completion_photo_reference"),
        _column("source_type"),
        _column("synthetic_marker", "boolean"),
    ),
)

GROUND_TRUTH_SCHEMA = TableSchema(
    table_name="ground_truth",
    filename="07_anomaly_ground_truth.csv",
    primary_keys=("work_id",),
    columns=(
        _column("work_id"),
        _column("injected_anomaly_count", "integer"),
        _column("injected_anomaly_types"),
        _column("expected_risk_score_0_100", "integer"),
        _column("expected_risk_class", "category"),
        _column("duplicate_group_reference", nullable=True),
        _column("label_usage_note"),
        _column("synthetic_marker", "boolean"),
    ),
)

OPERATIONAL_SCHEMAS = (
    MP_SCHEMA,
    ENTITIES_SCHEMA,
    WORKS_SCHEMA,
    PAYMENTS_SCHEMA,
    PROGRESS_SCHEMA,
    ASSETS_SCHEMA,
)

OPERATIONAL_SCHEMA_BY_TABLE = {schema.table_name: schema for schema in OPERATIONAL_SCHEMAS}

