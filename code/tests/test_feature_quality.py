"""Day-2.1 label-free model-eligibility and distribution-audit tests."""

from __future__ import annotations

import hashlib

from intelligence.features.quality import (
    build_feature_quality_profile,
    write_feature_quality_profile,
    write_refined_catalog,
)


def _sha256(path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def test_every_catalog_entry_has_current_generic_anomaly_metadata(feature_catalog):
    assert len(feature_catalog) == 76
    assert all(
        isinstance(item["generic_anomaly_eligible"], bool)
        and isinstance(item["generic_anomaly_notes"], str)
        and item["generic_anomaly_notes"]
        for item in feature_catalog
    )
    assert sum(item["model_eligible"] for item in feature_catalog) == 45
    assert sum(item["generic_anomaly_eligible"] for item in feature_catalog) == 32


def test_required_completion_and_routing_features_are_not_generic_candidates(
    feature_catalog,
):
    by_name = {item["name"]: item for item in feature_catalog}
    excluded = {
        "actual_duration_days",
        "completion_delay_days",
        "is_completed_as_of",
        "asset_record_count_as_of",
        "completion_marked_as_of",
        "uc_recorded_as_of",
        "handover_recorded_as_of",
        "public_use_recorded_as_of",
        "audit_recorded_as_of",
        "final_expenditure_inr_as_of",
    }
    assert all(not by_name[name]["generic_anomaly_eligible"] for name in excluded)


def test_zero_variance_features_cannot_be_generic_candidates(
    feature_table,
    feature_catalog,
):
    profile = build_feature_quality_profile(feature_table, feature_catalog)
    assert profile["zero_variance_features"] == [
        "vendor_hhi_as_of",
        "days_since_last_progress_report_as_of",
        "uc_recorded_as_of",
        "audit_recorded_as_of",
        "source_vs_asof_physical_progress_difference_pct",
    ]
    assert profile["near_zero_variance_features"] == [
        "zero_value_released_payment_count_as_of",
        "same_day_progress_extra_count_as_of",
        "source_vs_asof_expenditure_difference_inr",
    ]
    by_name = {item["name"]: item for item in profile["features"]}
    assert all(
        not by_name[name]["generic_anomaly_eligible"]
        for name in profile["zero_variance_features"]
    )


def test_payment_concentration_distributions_are_audited(feature_table, feature_catalog):
    assert feature_table["unique_vendor_count_as_of"].value_counts().sort_index().to_dict() == {
        0: 293,
        1: 2_707,
    }
    hhi = feature_table["vendor_hhi_as_of"]
    assert int(hhi.notna().sum()) == 2_706
    assert int(hhi.isna().sum()) == 294
    assert hhi.dropna().nunique() == 1
    assert hhi.dropna().iloc[0] == 1.0
    by_name = {item["name"]: item for item in feature_catalog}
    assert not by_name["vendor_hhi_as_of"]["model_eligible"]
    assert not by_name["vendor_hhi_as_of"]["generic_anomaly_eligible"]
    assert not by_name["unique_vendor_count_as_of"]["generic_anomaly_eligible"]


def test_audit_writes_metadata_without_rewriting_feature_values(
    feature_table,
    feature_catalog,
    project_paths,
    snapshot_date,
):
    feature_path = project_paths.processed_data_dir / "project_features.csv"
    before_hash = _sha256(feature_path)
    profile = build_feature_quality_profile(feature_table, feature_catalog)
    catalog_path = write_refined_catalog(project_paths, snapshot_date)
    quality_path = write_feature_quality_profile(profile, project_paths)
    after_hash = _sha256(feature_path)

    assert before_hash == after_hash
    assert feature_table.shape == (3_000, 76)
    assert catalog_path.parent == project_paths.processed_data_dir.resolve()
    assert quality_path.parent == project_paths.processed_data_dir.resolve()
    assert profile["audited_numeric_boolean_feature_count"] == 54
