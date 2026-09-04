"""Day-2 one-row feature snapshot and unified-profile regressions."""

from __future__ import annotations

import inspect
import json

import numpy as np
import pandas as pd
import pytest

from intelligence.features import builder, profile
from intelligence.features.aggregations import (
    aggregate_assets_as_of,
    aggregate_payments_as_of,
    aggregate_progress_as_of,
    safe_ratio,
)
from intelligence.features.builder import build_feature_diagnostics, write_feature_outputs
from intelligence.features.profile import build_project_profile


def test_project_features_are_exactly_one_row_per_work(feature_table, operational_bundle):
    assert feature_table.shape == (3_000, 76)
    assert feature_table["work_id"].notna().all()
    assert feature_table["work_id"].is_unique
    assert set(feature_table["work_id"]) == set(operational_bundle.works["work_id"])


def test_leakage_blacklist_and_raw_history_columns_are_absent(feature_table):
    lowered = [column.lower() for column in feature_table.columns]
    assert "duplicate_group_reference" not in feature_table
    assert not any("ground_truth" in column for column in lowered)
    assert not any("injected_anomaly" in column for column in lowered)
    assert not any("expected_risk" in column for column in lowered)
    assert not {"payment_id", "progress_id", "asset_id", "vendor_id"}.intersection(
        feature_table.columns
    )

    feature_source = inspect.getsource(builder) + inspect.getsource(profile)
    assert "load_evaluation_ground_truth" not in feature_source
    assert "07_anomaly_ground_truth" not in feature_source
    assert "load_official_supplements" not in feature_source


def test_histories_are_aggregated_independently_to_work(operational_bundle, snapshot_date):
    payment = aggregate_payments_as_of(operational_bundle.payments, snapshot_date)
    progress = aggregate_progress_as_of(operational_bundle.progress, snapshot_date)
    assets = aggregate_assets_as_of(operational_bundle.assets, snapshot_date)
    assert payment["work_id"].is_unique
    assert progress["work_id"].is_unique
    assert assets["work_id"].is_unique
    assert len(payment) <= len(operational_bundle.works)
    assert len(progress) <= len(operational_bundle.works)
    assert len(assets) <= len(operational_bundle.works)


def test_future_payment_releases_are_excluded(feature_table, operational_bundle, snapshot_date):
    as_of = pd.Timestamp(snapshot_date)
    included = operational_bundle.payments["payment_release_date"].le(as_of)
    assert int((~included).sum()) == 55
    assert feature_table["released_payment_count_as_of"].sum() == int(included.sum())
    assert feature_table["released_payment_total_inr_as_of"].sum() == int(
        operational_bundle.payments.loc[included, "payment_amount_inr"].sum()
    )
    assert feature_table["last_payment_release_date_as_of"].dropna().le(as_of).all()


def test_latest_progress_comes_from_visible_history(
    feature_table,
    operational_bundle,
    snapshot_date,
):
    as_of = pd.Timestamp(snapshot_date)
    visible = operational_bundle.progress.loc[
        operational_bundle.progress["report_date"].le(as_of)
    ].sort_values(["work_id", "report_date", "progress_id"], kind="stable")
    latest = visible.groupby("work_id")["physical_progress_pct"].last()
    observed = feature_table.set_index("work_id")["latest_physical_progress_pct_as_of"]
    pd.testing.assert_series_equal(
        observed.loc[latest.index],
        latest,
        check_names=False,
        check_dtype=False,
    )
    assert int((operational_bundle.progress["report_date"] > as_of).sum()) == 0


def test_ratios_use_safe_denominators(feature_table):
    result = safe_ratio(pd.Series([10, 10, 10]), pd.Series([2, 0, -1]))
    assert result.iloc[0] == 5
    assert pd.isna(result.iloc[1])
    assert pd.isna(result.iloc[2])
    no_sanction = feature_table["sanctioned_amount_inr"].isna() | feature_table[
        "sanctioned_amount_inr"
    ].le(0)
    assert feature_table.loc[no_sanction, "expenditure_to_sanction_pct_as_of"].isna().all()
    numeric = feature_table.select_dtypes(include=["number"])
    assert not np.isinf(numeric.to_numpy(dtype="float64", na_value=np.nan)).any()


def test_lifecycle_stage_rule_is_deterministic(feature_table):
    assert feature_table["lifecycle_stage"].value_counts().to_dict() == {
        "COMPLETION": 1_929,
        "EXECUTION": 801,
        "PRE_SANCTION": 270,
    }
    assert feature_table.loc[feature_table["is_rejected"], "lifecycle_stage"].eq(
        "PRE_SANCTION"
    ).all()
    assert feature_table.loc[feature_table["is_completed_as_of"], "lifecycle_stage"].eq(
        "COMPLETION"
    ).all()


def test_completion_and_closure_flags_obey_event_dates(feature_table, snapshot_date):
    as_of = pd.Timestamp(snapshot_date)
    assert int(feature_table["is_completed_as_of"].sum()) == 1_929
    assert int(feature_table["completion_marked_as_of"].sum()) == 332
    assert int(feature_table["uc_recorded_as_of"].sum()) == 0
    assert int(feature_table["handover_recorded_as_of"].sum()) == 101
    assert int(feature_table["public_use_recorded_as_of"].sum()) == 55
    assert int(feature_table["audit_recorded_as_of"].sum()) == 0
    assert feature_table["completion_date_as_of"].dropna().le(as_of).all()


def test_asset_aggregation_remains_one_row_when_multiple_assets_exist(
    operational_bundle,
    snapshot_date,
):
    original = operational_bundle.assets.iloc[[0]].copy()
    duplicate = original.copy()
    duplicate["asset_id"] = duplicate["asset_id"].astype("string") + "-SECOND"
    multiple = pd.concat([original, duplicate], ignore_index=True)
    aggregate = aggregate_assets_as_of(multiple, snapshot_date)
    assert len(aggregate) == 1
    assert aggregate.iloc[0]["asset_record_count_as_of"] == 2


def test_catalog_exactly_covers_features_and_declares_eligibility(
    feature_table,
    feature_catalog,
):
    assert [entry["name"] for entry in feature_catalog] == feature_table.columns.tolist()
    assert all(isinstance(entry["model_eligible"], bool) for entry in feature_catalog)
    assert all(
        {
            "name",
            "category",
            "description",
            "formula_or_source",
            "data_type",
            "model_eligible",
            "generic_anomaly_eligible",
            "generic_anomaly_notes",
            "leakage_notes",
        }
        == set(entry)
        for entry in feature_catalog
    )
    assert sum(entry["model_eligible"] for entry in feature_catalog) == 45
    assert sum(entry["generic_anomaly_eligible"] for entry in feature_catalog) == 32


@pytest.mark.parametrize("lifecycle_stage", ["PRE_SANCTION", "EXECUTION", "COMPLETION"])
def test_project_profile_examples_are_resolved_and_as_of_safe(
    lifecycle_stage,
    feature_table,
    operational_bundle,
    snapshot_date,
):
    work_id = feature_table.loc[
        feature_table["lifecycle_stage"].eq(lifecycle_stage), "work_id"
    ].iloc[0]
    project = build_project_profile(
        work_id,
        operational_bundle,
        snapshot_date,
        feature_table=feature_table,
    )
    expected_work = operational_bundle.works.set_index("work_id").loc[work_id]
    assert project.work_context["work_id"] == work_id
    assert project.mp_context["mp_id"] == expected_work["mp_id"]
    if pd.isna(expected_work["implementing_agency_id"]):
        assert project.implementing_agency_context is None
    else:
        assert project.implementing_agency_context["entity_id"] == expected_work[
            "implementing_agency_id"
        ]

    as_of = pd.Timestamp(snapshot_date)
    assert project.released_payments_as_of["payment_release_date"].le(as_of).all()
    assert project.progress_reports_as_of["report_date"].le(as_of).all()
    for date_column in [
        "completion_date",
        "completion_marked_date",
        "utilization_certificate_date",
        "handover_date",
        "public_use_date",
        "audit_date",
    ]:
        assert project.asset_records_as_of[date_column].dropna().le(as_of).all()

    expected_feature = feature_table.loc[feature_table["work_id"].eq(work_id)].iloc[0]
    actual_feature = pd.Series(project.derived_features).reindex(expected_feature.index)
    expected_feature = expected_feature.astype("object").where(expected_feature.notna(), None)
    actual_feature = actual_feature.astype("object").where(actual_feature.notna(), None)
    pd.testing.assert_series_equal(
        actual_feature,
        expected_feature,
        check_names=False,
        check_dtype=False,
    )


def test_current_as_of_diagnostics_are_reproducible(
    feature_table,
    operational_bundle,
    snapshot_date,
):
    diagnostics = build_feature_diagnostics(
        operational_bundle,
        feature_table,
        snapshot_date,
    )
    assert diagnostics["future_payment_release_rows_excluded"] == 55
    assert diagnostics["payment_rows_included_as_of"] == 9_672
    assert diagnostics["payment_value_inr_included_as_of"] == 4_984_010_000
    assert diagnostics["future_progress_rows_excluded"] == 0
    assert diagnostics["works_with_zero_progress_reports_as_of"] == 270
    assert diagnostics["works_completed_as_of"] == 1_929
    assert diagnostics["future_asset_events_excluded"] == {
        "completion_date": 0,
        "completion_marked_date": 1_597,
        "utilization_certificate_date": 1_890,
        "handover_date": 1_828,
        "public_use_date": 1_874,
        "audit_date": 647,
    }


def test_required_feature_artifacts_are_written_only_under_processed(
    feature_table,
    project_paths,
    snapshot_date,
):
    feature_path, catalog_path = write_feature_outputs(
        feature_table,
        project_paths,
        snapshot_date,
    )
    expected_parent = (project_paths.project_root / "data" / "processed").resolve()
    assert feature_path.parent == expected_parent
    assert catalog_path.parent == expected_parent
    assert feature_path.name == "project_features.csv"
    assert catalog_path.name == "feature_catalog.json"

    persisted = pd.read_csv(feature_path, encoding="utf-8")
    catalog_payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert persisted.shape == feature_table.shape
    assert persisted["work_id"].is_unique
    assert catalog_payload["column_count"] == len(feature_table.columns)
    assert catalog_payload["model_eligible_feature_count"] == 45
    assert catalog_payload["generic_anomaly_eligible_feature_count"] == 32
    assert [item["name"] for item in catalog_payload["features"]] == list(
        feature_table.columns
    )
    assert not (project_paths.demo_data_dir / feature_path.name).exists()
    assert not (project_paths.demo_data_dir / catalog_path.name).exists()
